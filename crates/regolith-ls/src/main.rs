//! `regolith-ls`: LSP over stdio (WO-38 deliverable 1). Logs go to
//! stderr (`tracing`, house rule); stdout is the LSP transport only.

use std::time::{Duration, Instant};

use crossbeam_channel::RecvTimeoutError;
use lsp_server::{Connection, ExtractError, Message, Notification, Request, RequestId, Response};
use lsp_types::notification::{
    DidChangeTextDocument, DidCloseTextDocument, DidOpenTextDocument, DidSaveTextDocument,
    Notification as _,
};
use lsp_types::request::{
    CodeActionRequest, Completion, DocumentSymbolRequest, FoldingRangeRequest, Formatting,
    GotoDefinition, HoverRequest, References, Rename, SemanticTokensFullRequest,
};
use lsp_types::{
    CompletionResponse, DidChangeTextDocumentParams, DidOpenTextDocumentParams,
    GotoDefinitionResponse, InitializeParams, PublishDiagnosticsParams,
};
use regolith_ls::diagnostics::file_uri;
use regolith_ls::server::{capabilities, root_from_initialize, Server};

fn main() {
    tracing_subscriber::fmt()
        .with_writer(std::io::stderr)
        .with_env_filter(std::env::var("REGOLITH_LS_LOG").unwrap_or_else(|_| "info".to_string()))
        .init();

    tracing::info!("regolith-ls starting (stdio transport)");
    let (connection, io_threads) = Connection::stdio();

    let init_result = run(&connection);
    if let Err(err) = init_result {
        tracing::error!(?err, "regolith-ls exited with an error");
    }

    io_threads.join().ok();
    tracing::info!("regolith-ls shut down");
}

/// The initialize handshake plus the main dispatch loop. Returns once
/// the client sends `shutdown`/the channel closes.
fn run(connection: &Connection) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let (id, params) = connection.initialize_start()?;
    let init_params: InitializeParams = serde_json::from_value(params)?;
    let root = root_from_initialize(&init_params);
    tracing::info!(%root, "workspace root discovered");

    let caps = capabilities();
    let init_response = serde_json::json!({
        "capabilities": caps,
        "serverInfo": { "name": "regolith-ls", "version": env!("CARGO_PKG_VERSION") },
    });
    connection.initialize_finish(id, init_response)?;

    let mut server = Server::new(root);
    // The debounced semantic-tier deadline (deliverable 3): `None` when
    // no workspace recheck is pending, `Some(deadline)` once a change
    // has come in and not yet been settled for `DEBOUNCE`. Every new
    // change PUSHES the deadline out (debounce, not throttle).
    let mut pending_deadline: Option<Instant> = None;

    loop {
        let timeout =
            pending_deadline.map(|deadline| deadline.saturating_duration_since(Instant::now()));
        let recv = match timeout {
            Some(remaining) => connection.receiver.recv_timeout(remaining),
            None => connection
                .receiver
                .recv()
                .map_err(|_| RecvTimeoutError::Disconnected),
        };
        match recv {
            Ok(Message::Request(req)) => {
                if connection.handle_shutdown(&req)? {
                    break;
                }
                handle_request(connection, &mut server, req)?;
            }
            Ok(Message::Notification(not)) => {
                if is_change_notification(&not) {
                    handle_notification(connection, &mut server, not)?;
                    pending_deadline = Some(Instant::now() + DEBOUNCE);
                } else {
                    handle_notification(connection, &mut server, not)?;
                }
            }
            Ok(Message::Response(_)) => {}
            Err(RecvTimeoutError::Timeout) => {
                // The debounce window elapsed with no further edits:
                // run the semantic-tier (full workspace) check now.
                pending_deadline = None;
                publish_all(connection, &server)?;
            }
            Err(RecvTimeoutError::Disconnected) => break,
        }
    }
    Ok(())
}

/// The two-tier debounce window (deliverable 3): ~300ms of quiescence
/// after the last edit before the semantic-tier workspace check runs.
const DEBOUNCE: Duration = Duration::from_millis(300);

/// Whether `not` is the notification that drives the debounced
/// semantic-tier recheck (`didChange`) as opposed to one that already
/// runs its own immediate full check (`didOpen`/`didSave`) or needs
/// none (`didClose`).
fn is_change_notification(not: &Notification) -> bool {
    not.method == DidChangeTextDocument::METHOD
}

type DynErr = Box<dyn std::error::Error + Send + Sync>;

/// Dispatch one request to its handler, or reply with `MethodNotFound`.
fn handle_request(
    connection: &Connection,
    server: &mut Server,
    req: Request,
) -> Result<(), DynErr> {
    let req = match cast_req::<HoverRequest>(req) {
        Ok((id, params)) => {
            let result = server.hover(
                &params.text_document_position_params.text_document.uri,
                params.text_document_position_params.position,
            );
            return send_response(connection, id, result);
        }
        Err(req) => req,
    };
    let req = match cast_req::<DocumentSymbolRequest>(req) {
        Ok((id, params)) => {
            let result = server.document_symbols(&params.text_document.uri);
            return send_response(connection, id, result);
        }
        Err(req) => req,
    };
    let req = match cast_req::<FoldingRangeRequest>(req) {
        Ok((id, params)) => {
            let result = server.folding_ranges(&params.text_document.uri);
            return send_response(connection, id, result);
        }
        Err(req) => req,
    };
    let req = match cast_req::<Formatting>(req) {
        Ok((id, params)) => {
            let result = server.format(&params.text_document.uri);
            return send_response(connection, id, result);
        }
        Err(req) => req,
    };
    let req = match cast_req::<SemanticTokensFullRequest>(req) {
        Ok((id, params)) => {
            let result = server.semantic_tokens(&params.text_document.uri);
            return send_response(connection, id, result);
        }
        Err(req) => req,
    };
    let req = match cast_req::<CodeActionRequest>(req) {
        Ok((id, params)) => {
            let result = server.code_actions(&params.context.diagnostics);
            return send_response(connection, id, Some(result));
        }
        Err(req) => req,
    };
    let req = match cast_req::<Completion>(req) {
        Ok((id, params)) => {
            let items = server.completions(
                &params.text_document_position.text_document.uri,
                params.text_document_position.position,
            );
            return send_response(connection, id, Some(CompletionResponse::Array(items)));
        }
        Err(req) => req,
    };
    let Some(req) = handle_nav_request(connection, server, req)? else {
        return Ok(());
    };
    tracing::warn!(method = %req.method, "unhandled request method");
    let resp = Response::new_err(
        req.id,
        lsp_server::ErrorCode::MethodNotFound as i32,
        format!("method not implemented: {}", req.method),
    );
    connection.sender.send(Message::Response(resp))?;
    Ok(())
}

/// The navigation half of request dispatch (deliverable 6:
/// definition/references/rename), split out so `handle_request` stays
/// under the workspace line-count lint.
///
/// Returns `Ok(Some(req))` when none of these methods matched (the
/// caller continues dispatch), `Ok(None)` once a response has been
/// sent.
fn handle_nav_request(
    connection: &Connection,
    server: &mut Server,
    req: Request,
) -> Result<Option<Request>, DynErr> {
    let req = match cast_req::<GotoDefinition>(req) {
        Ok((id, params)) => {
            let result = server
                .definition(
                    &params.text_document_position_params.text_document.uri,
                    params.text_document_position_params.position,
                )
                .map(GotoDefinitionResponse::Array);
            send_response(connection, id, result)?;
            return Ok(None);
        }
        Err(req) => req,
    };
    let req = match cast_req::<References>(req) {
        Ok((id, params)) => {
            let result = server.references(
                &params.text_document_position.text_document.uri,
                params.text_document_position.position,
            );
            send_response(connection, id, result)?;
            return Ok(None);
        }
        Err(req) => req,
    };
    let req = match cast_req::<Rename>(req) {
        Ok((id, params)) => {
            let outcome = server.rename(
                &params.text_document_position.text_document.uri,
                params.text_document_position.position,
                &params.new_name,
            );
            match outcome {
                Ok(edit) => send_response(connection, id, Some(edit))?,
                Err(reason) => {
                    tracing::warn!(%reason, "rename refused");
                    let resp =
                        Response::new_err(id, lsp_server::ErrorCode::RequestFailed as i32, reason);
                    connection.sender.send(Message::Response(resp))?;
                }
            }
            return Ok(None);
        }
        Err(req) => req,
    };
    Ok(Some(req))
}

/// Dispatch one notification: document sync drives `check` and
/// publishes diagnostics (deliverable 3).
fn handle_notification(
    connection: &Connection,
    server: &mut Server,
    not: Notification,
) -> Result<(), DynErr> {
    let not = match cast_not::<DidOpenTextDocument>(not) {
        Ok(params) => {
            open_and_check(connection, server, params)?;
            return Ok(());
        }
        Err(not) => not,
    };
    let not = match cast_not::<DidChangeTextDocument>(not) {
        Ok(params) => {
            change_and_check(connection, server, params)?;
            return Ok(());
        }
        Err(not) => not,
    };
    let not = match cast_not::<DidSaveTextDocument>(not) {
        Ok(_params) => {
            publish_all(connection, server)?;
            return Ok(());
        }
        Err(not) => not,
    };
    let not = match cast_not::<DidCloseTextDocument>(not) {
        Ok(params) => {
            server.close(&params.text_document.uri);
            return Ok(());
        }
        Err(not) => not,
    };
    tracing::debug!(method = %not.method, "unhandled notification method");
    Ok(())
}

fn open_and_check(
    connection: &Connection,
    server: &mut Server,
    params: DidOpenTextDocumentParams,
) -> Result<(), DynErr> {
    server.open(params.text_document.uri, params.text_document.text);
    publish_all(connection, server)
}

fn change_and_check(
    connection: &Connection,
    server: &mut Server,
    params: DidChangeTextDocumentParams,
) -> Result<(), DynErr> {
    // Full-text sync v1 (deliverable 1): the last content change carries
    // the entire new document text.
    let Some(change) = params.content_changes.into_iter().last() else {
        return Ok(());
    };
    let uri = params.text_document.uri;
    server.open(uri.clone(), change.text);

    // Syntax tier (deliverable 3, SLO < 100ms): reparse and publish
    // diagnostics for JUST the edited file immediately, verbatim per
    // D111. The semantic tier (the full workspace `check`, which needs
    // `regolith-sem`/`regolith-ir`/`regolith-oblig`) is debounced by the
    // caller (the ~300ms quiescence window in `run`'s main loop) rather
    // than run here on every keystroke.
    if let Some(path) = regolith_ls::diagnostics::uri_to_path(&uri) {
        let text = server.text(&uri).unwrap_or_default().to_string();
        let diags = regolith_ls::diagnostics::syntax_diagnostics_for_text(&path, &text);
        let params = PublishDiagnosticsParams {
            uri,
            diagnostics: diags,
            version: None,
        };
        let not = Notification::new(
            lsp_types::notification::PublishDiagnostics::METHOD.to_string(),
            params,
        );
        connection.sender.send(Message::Notification(not))?;
    }
    Ok(())
}

/// Run the workspace check pipeline and publish diagnostics for every
/// affected file (deliverable 3: verbatim mapping, no server-side
/// filtering).
fn publish_all(connection: &Connection, server: &Server) -> Result<(), DynErr> {
    let Some(by_file) = server.check_diagnostics() else {
        tracing::warn!(
            "workspace check failed at the infrastructure level; no diagnostics published"
        );
        return Ok(());
    };
    for (path, diags) in by_file {
        let Some(uri) = file_uri(&path) else { continue };
        let params = PublishDiagnosticsParams {
            uri,
            diagnostics: diags,
            version: None,
        };
        let not = Notification::new(
            lsp_types::notification::PublishDiagnostics::METHOD.to_string(),
            params,
        );
        connection.sender.send(Message::Notification(not))?;
    }
    Ok(())
}

fn send_response<T: serde::Serialize>(
    connection: &Connection,
    id: RequestId,
    result: T,
) -> Result<(), DynErr> {
    let resp = Response::new_ok(id, serde_json::to_value(result)?);
    connection.sender.send(Message::Response(resp))?;
    Ok(())
}

fn cast_req<R>(req: Request) -> Result<(RequestId, R::Params), Request>
where
    R: lsp_types::request::Request,
{
    match req.extract::<R::Params>(R::METHOD) {
        Ok(pair) => Ok(pair),
        Err(ExtractError::MethodMismatch(req)) => Err(req),
        Err(ExtractError::JsonError { method, error }) => {
            tracing::error!(%method, %error, "malformed request params");
            Err(Request::new(
                RequestId::from(0),
                method,
                serde_json::Value::Null,
            ))
        }
    }
}

fn cast_not<N>(not: Notification) -> Result<N::Params, Notification>
where
    N: lsp_types::notification::Notification,
{
    match not.extract::<N::Params>(N::METHOD) {
        Ok(params) => Ok(params),
        Err(ExtractError::MethodMismatch(not)) => Err(not),
        Err(ExtractError::JsonError { method, error }) => {
            tracing::error!(%method, %error, "malformed notification params");
            Err(Notification::new(method, serde_json::Value::Null))
        }
    }
}
