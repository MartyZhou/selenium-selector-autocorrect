# Selenium Selector AutoCorrect

A Python package that automatically corrects Selenium element selectors using AI when they fail, reducing test maintenance and improving test reliability.

## Features

- **Automatic Selector Correction**: When a WebDriverWait times out, the package uses AI to analyze the page and suggest working alternatives
- **Local AI Integration**: Uses a local AI service with OpenAI-compatible API
- **Correction Tracking**: Records all corrections with source file and line information
- **Optional Auto-Update**: Can automatically update test files with corrected selectors
- **Zero Code Changes**: Works by hooking into Selenium's WebDriverWait

## Installation

```bash
pip install selenium-selector-autocorrect
```

## Quick Start

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_selector_autocorrect import install_auto_correct_hook

install_auto_correct_hook()

driver = webdriver.Chrome()
driver.get("https://example.com")

element = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.ID, "some-element"))
)
```

## AI Service Setup

This package requires a local AI service with an OpenAI-compatible API. We recommend using **[VS Code Copilot as Service](https://marketplace.visualstudio.com/items?itemName=MartyZhou.vscode-copilot-as-service)**, which exposes GitHub Copilot through a local HTTP server.

### Installing VS Code Copilot as Service

1. Install from VS Code Marketplace or run:
   ```bash
   code --install-extension MartyZhou.vscode-copilot-as-service
   ```

2. The extension automatically starts a server on `http://localhost:8765`

3. Requires an active GitHub Copilot subscription


## Configuration

Configure via environment variables:

- `LOCAL_AI_API_URL`: URL of local AI service (default: `http://localhost:8765`)
- `SELENIUM_AUTO_CORRECT`: Enable/disable auto-correction (default: `"1"`)
- `SELENIUM_SUGGEST_BETTER`: Suggest better selectors for found elements (default: `"0"`)
- `SELENIUM_AUTO_UPDATE_TESTS`: Auto-update test files with corrections (default: `"0"`)

### Example

```python
import os

os.environ['LOCAL_AI_API_URL'] = 'http://localhost:8765'
os.environ['SELENIUM_AUTO_CORRECT'] = '1'
os.environ['SELENIUM_AUTO_UPDATE_TESTS'] = '1'  # Enable auto-update
```

## Usage

### Basic Usage

```python
from selenium_selector_autocorrect import install_auto_correct_hook

install_auto_correct_hook()
```

### Advanced Usage

```python
from selenium_selector_autocorrect import (
    install_auto_correct_hook,
    get_auto_correct,
    get_correction_tracker,
    export_corrections_report
)

install_auto_correct_hook()

auto_correct = get_auto_correct()
auto_correct.enabled = True
auto_correct.suggest_better_selectors = False

# Export corrections report at end of test run
tracker = get_correction_tracker()
export_corrections_report("corrections_report.json")
tracker = get_correction_tracker()
export_corrections_report("corrections_report.json")

print(f"Total corrections: {len(tracker.get_corrections())}")
print(f"Successful corrections: {len(tracker.get_successful_corrections())}")
```

### Custom AI Provider

```python
from selenium_selector_autocorrect import AIProvider, configure_provider

class CustomAIProvider(AIProvider):
    def is_available(self) -> bool:
        return True
    
    def suggest_selector(self, system_prompt: str, user_prompt: str):))
```

## How It Works

1. **Hook Installation**: Patches `WebDriverWait.until()` to add auto-correction
2. **Timeout Detection**: When a selector times out, the original exception is caught
3. **Page Analysis**: JavaScript extracts visible elements and their attributes
4. **AI Suggestion**: Sends page context to AI provider for selector suggestion
5. **Verification**: Tests the suggested selector
6. **Success Handling**: If successful, records the correction and optionally updates the test file
7. **Fallback**: If correction fails, raises the original TimeoutException

## AI Provider Setup

### Local AI Service

The package requires a local AI service with OpenAI-compatible API:

```bash
POST http://localhost:8765/v1/chat/completions
```

For file auto-updates:
```bash
POST http://localhost:8765/v1/workspace/files/read
POST http://localhost:8765/v1/workspace/files/edit
## Correction Reports

Export correction reports in JSON format:

```python
from selenium_selector_autocorrect import export_corrections_report

export_corrections_report("corrections_report.json")
```

Report format:
```json
{
  "corrections": [
    {
      "original_by": "id",
      "original_value": "old-selector",
      "corrected_by": "css selector",
      "corrected_value": ".new-selector",
      "success": true,
      "test_file": "/path/to/test.py",
      "test_line": 42,
      "timestamp": "2024-01-31T10:30:00"
    }
  ],
  "summary": {
    "total": 10,
    "successful": 8,
    "generated_at": "2024-01-31T10:35:00"
  }
}
```

## Best Practices

1. **Install Once**: Call `install_auto_correct_hook()` once at test suite startup (e.g., in `conftest.py`)
2. **Review Corrections**: Regularly review correction reports to identify brittle selectors
3. **Update Tests**: Use auto-update sparingly and review changes before committing
4. **Monitor AI Service**: Ensure your AI service is running and responsive
5. **Use Strong Selectors**: The tool helps with failures but writing robust selectors is still preferred

## Requirements

- Python >= 3.8
- selenium >= 4.0.0
- requests >= 2.25.0

## License

MITInstall hook once at test suite startup (e.g., in conftest.py)
2. Review correction reports regularly to identify brittle selectors
3. Use auto-update sparingly and review changes before committing
4. Ensure your AI service is running and responsive
5. Write robust selectors - the tool helps with failures but prevention is better

When contributing:
1. Follow PEP 8 style guidelines
2. Add tests for new features
3. Update documentation
4. No emojis in code or documentation

## Troubleshooting

### AI Service Not Available

Contributions are welcome! Please:
1. Follow PEP 8 style guidelines
2. Add tests for new features
3. Update documentation
4. Maintain consistency with existing code

**Possible causes**:
- `SELENIUM_AUTO_UPDATE_TESTS` not set to `"1"`
- Test file path not detected correctly
- Selector string not found in source file (check quotes)

### No Corrections Happening
Solution: Ensure your local AI service is running on the configured port.

### Test File Not Updated

Possible causes:
- `SELENIUM_AUTO_UPDATE_TESTS` not set to "1"
- Test file path not detected correctly
- Selector string not found in source file

### No Corrections Happening

Check:
1. Hook is installed - look for log message
2. AI service is available - check `get_auto_correct().is_service_available()`
3. Auto-correct is enabled - c
See CHANGELOG.md for version history and changes.
