# VM Agent Notes

Goal: Improve Hyper-V guest control by scoping desktop actions to the VMConnect window.

## Added Tool
- `vm` tool (JSON payload) for window-scoped focus, click, type, press, and observe.
- Uses `pygetwindow` to locate the VMConnect window by name and `pyautogui` for input.

## Example Payloads
```json
{"action":"focus","vm_name":"Win11_Gen2_clean"}
```
```json
{"action":"click","vm_name":"Win11_Gen2_clean","x":640,"y":360}
```
```json
{"action":"type","text":"cmd"}
```
```json
{"action":"press","key":"enter"}
```
```json
{"action":"observe","vm_name":"Win11_Gen2_clean","path":"C:\\\\Users\\\\codym\\\\data\\\\runs\\\\latest\\\\vm.png"}
```

## Dependencies
- `pyautogui`
- `pygetwindow`
- `pywin32` (optional, enables `PrintWindow` capture to avoid black screenshots)

## Next Improvements
- Add automatic VMConnect launch if window not found.
- Add configurable window match strategy (exact title or regex).
- Add optional cropping/offset compensation for window chrome.
