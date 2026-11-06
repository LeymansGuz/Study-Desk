; Compress files independently. A solid archive changes almost every byte when
; a single script changes, defeating signed content-defined update downloads.
; Included by Tauri before any installer data. Keep its standard installer logic.
SetCompressor /FINAL lzma
