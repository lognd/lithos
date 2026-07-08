//! `regolith-ls`: LSP over stdio (WO-38 deliverable 1). Logs go to
//! stderr (`tracing`, house rule); stdout is the LSP transport only.

use lsp_server::{Connection, ExtractError, Message, Notification, Request, RequestId, Response};
use lsp_types::notification::{
    DidChangeTextDocument, DidCloseTextDocument, DidOpenTextDocument, DidSaveTextDocument,
    Notification as _,
};
use lsp_types::request::{
    CodeActionRequest, Completion, DocumentSymbolRequest, FoldingRangeRequest, Formatting,
    HoverRequest, SemanticTokensFullRequest,
};
use lsp_types::{
    CompletionResponse, DidChangeTextDocumentParams, DidOpenTextDocumentParams, InitializeParams,
    PublishDiagnosticsParams,
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

    for msg in &connection.receiver {
        match msg {
            Message::Request(req) => {
                if connection.handle_shutdown(&req)? {
                    break;
                }
                handle_request(connection, &mut server, req)?;
            }
            Message::Notification(not) => handle_notification(connection, &mut server, not)?,
            Message::Response(_) => {}
        }
    }
    Ok(())
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
        Ok((id, _params)) => {
            let items = server.completions();
            return send_response(connection, id, Some(CompletionResponse::Array(items)));
        }
        Err(req) => req,
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
    if let Some(change) = params.content_changes.into_iter().last() {
        server.open(params.text_document.uri, change.text);
    }
    publish_all(connection, server)
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
