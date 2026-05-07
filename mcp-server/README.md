# MCP Server — Functional-Emotional Readout

Minimalny serwer MCP (stdio) do obsługi protokołu readout.

## Wymagania

- Python 3.11+
- `mcp` SDK ≥ 1.0.0

## Instalacja

```bash
cd mcp-server
pip install -e .
```

Lub z dev dependencies (testy):

```bash
pip install -e ".[dev]"
```

## Uruchomienie

Serwer działa przez stdio — podłącz go do swojego klienta MCP (Claude Code, własny klient):

```bash
python server.py
```

## Konfiguracja w Claude Code

Dodaj do `.claude/mcp.json` (lub globalnego `~/claude/mcp.json`):

```json
{
  "mcpServers": {
    "readout": {
      "command": "python",
      "args": ["/ścieżka/do/mcp-server/server.py"]
    }
  }
}
```

## Narzędzia

### `get_readout()`

Zwraca aktualny readout lub komunikat o braku readoutu.

```
Wejście: brak
Wyjście: JSON readoutu lub informacja o braku
```

### `set_readout(readout)`

Model proaktywnie flaguje stan. Readout jest walidowany, zapisywany do `readouts.jsonl` i zwracany operatorowi.

```
Wejście: readout JSON (pełny schemat w PROTOCOL.md)
Wyjście: potwierdzenie + readout
```

## Persistence

Readouty są dopisywane do `readouts.jsonl` w katalogu roboczym (gdzie serwer jest uruchomiony). Jeden readout = jedna linia JSON.

Żeby wyłączyć persistence: usuń wywołanie `_persist()` w `server.py` lub przekieruj do `/dev/null`.

## Testy

```bash
pytest tests/ -v
```

## Znane ograniczenia

- Jeden aktywny readout w pamięci — `get_readout()` zwraca tylko najnowszy
- Brak autentykacji — przeznaczony do lokalnego użytku
- Brak multi-session routing — jeden serwer = jedna sesja
