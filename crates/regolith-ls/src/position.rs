//! F111: the ONE byte-offset <-> UTF-16 line/character converter.
//!
//! Regolith spans are byte offsets into UTF-8 source text (AD-3/AD-7);
//! LSP positions are UTF-16 code-unit line/character pairs. Every
//! boundary crossing (diagnostics, hover ranges, edits, symbols) goes
//! through [`LineIndex`] -- a second ad-hoc conversion anywhere else is
//! the classic LSP corruption bug this module exists to prevent.

use lsp_types::{Position, Range};

/// A precomputed table of line-start byte offsets plus the UTF-16 width
/// of every line, letting byte offset <-> LSP `Position` conversion run
/// in O(log n) without rescanning the text.
#[derive(Debug, Clone)]
pub struct LineIndex {
    /// Byte offset of the start of each line (line 0 starts at 0).
    line_starts: Vec<u32>,
    /// The full source text, kept to compute UTF-16 offsets within a line.
    text: String,
}

impl LineIndex {
    /// Build a line index over `text`.
    #[must_use]
    pub fn new(text: &str) -> LineIndex {
        let mut line_starts = vec![0u32];
        for (i, b) in text.bytes().enumerate() {
            if b == b'\n' {
                #[allow(clippy::cast_possible_truncation)]
                line_starts.push((i + 1) as u32);
            }
        }
        LineIndex {
            line_starts,
            text: text.to_string(),
        }
    }

    /// Convert a UTF-8 byte offset into an LSP UTF-16 `Position`. Offsets
    /// past the end of the text clamp to the last valid position.
    #[must_use]
    pub fn position(&self, byte_offset: usize) -> Position {
        #[allow(clippy::cast_possible_truncation)]
        let byte_offset = (byte_offset as u32).min(self.text.len().try_into().unwrap_or(u32::MAX));
        let line = match self.line_starts.binary_search(&byte_offset) {
            Ok(l) => l,
            Err(l) => l - 1,
        };
        let line_start = self.line_starts[line] as usize;
        let line_end = self
            .line_starts
            .get(line + 1)
            .map_or(self.text.len(), |&s| s as usize);
        let byte_offset = byte_offset as usize;
        let clamped_end = byte_offset.min(line_end);
        let line_text = &self.text[line_start..clamped_end.max(line_start)];
        #[allow(clippy::cast_possible_truncation)]
        let character = line_text.encode_utf16().count() as u32;
        #[allow(clippy::cast_possible_truncation)]
        Position {
            line: line as u32,
            character,
        }
    }

    /// Convert an LSP UTF-16 `Position` back into a UTF-8 byte offset.
    /// Out-of-range lines/characters clamp to the nearest valid offset.
    #[must_use]
    pub fn offset(&self, position: Position) -> usize {
        let line = (position.line as usize).min(self.line_starts.len() - 1);
        let line_start = self.line_starts[line] as usize;
        let line_end = self
            .line_starts
            .get(line + 1)
            .map_or(self.text.len(), |&s| s as usize);
        let line_text = &self.text[line_start..line_end];

        let mut utf16_count = 0u32;
        for (byte_idx, ch) in line_text.char_indices() {
            if utf16_count >= position.character {
                return line_start + byte_idx;
            }
            utf16_count += u32::try_from(ch.len_utf16()).unwrap_or(1);
        }
        line_end
    }

    /// Convert a byte range `[start, end)` into an LSP `Range`.
    #[must_use]
    pub fn range(&self, start: usize, end: usize) -> Range {
        Range {
            start: self.position(start),
            end: self.position(end),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::LineIndex;
    use lsp_types::Position;

    #[test]
    fn ascii_single_line_round_trips() {
        let idx = LineIndex::new("hello world");
        let pos = idx.position(6);
        assert_eq!(
            pos,
            Position {
                line: 0,
                character: 6
            }
        );
        assert_eq!(idx.offset(pos), 6);
    }

    #[test]
    fn multiple_lines_track_line_starts() {
        let text = "part a:\n  mass: 5 g\nend\n";
        let idx = LineIndex::new(text);
        // "mass" starts at byte 10, on line 1, column 2.
        let byte = text.find("mass").unwrap();
        let pos = idx.position(byte);
        assert_eq!(pos.line, 1);
        assert_eq!(pos.character, 2);
        assert_eq!(idx.offset(pos), byte);
    }

    #[test]
    fn multi_byte_content_uses_utf16_widths() {
        // Each of these emoji is 4 bytes UTF-8 / 2 UTF-16 code units
        // (a surrogate pair) -- the classic corruption case (F111).
        let text = "# comment with unicode: caf\u{e9} \u{1F600}\npart a:\n";
        let idx = LineIndex::new(text);
        let newline_byte = text.find('\n').unwrap();
        let pos = idx.position(newline_byte);
        assert_eq!(pos.line, 0);
        // "# comment with unicode: caf" (28 ascii chars) + e-acute (1 utf16
        // unit) + space (1) + emoji (2 utf16 units, surrogate pair) = 32.
        let expected_utf16: u32 = text[..newline_byte]
            .encode_utf16()
            .count()
            .try_into()
            .unwrap();
        assert_eq!(pos.character, expected_utf16);
        assert_eq!(idx.offset(pos), newline_byte);
    }

    #[test]
    fn offset_at_non_ascii_boundary_is_stable() {
        let text = "x = \u{1F600}\n";
        let idx = LineIndex::new(text);
        // Position right after the emoji (2 utf16 units past its start).
        let emoji_byte = text.find('\u{1F600}').unwrap();
        let before = idx.position(emoji_byte);
        let after_offset = idx.offset(Position {
            line: before.line,
            character: before.character + 2,
        });
        assert_eq!(after_offset, emoji_byte + '\u{1F600}'.len_utf8());
    }

    #[test]
    fn offset_past_end_of_text_clamps() {
        let idx = LineIndex::new("abc\n");
        let pos = idx.position(1000);
        assert_eq!(idx.offset(pos), 4);
    }

    #[test]
    fn empty_text_has_one_line() {
        let idx = LineIndex::new("");
        let pos = idx.position(0);
        assert_eq!(
            pos,
            Position {
                line: 0,
                character: 0
            }
        );
    }
}
