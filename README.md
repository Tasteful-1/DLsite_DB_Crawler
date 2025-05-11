# DLsite_DB_Scraper

A Python tool for systematically collecting product information and images from DLsite and storing them in a local database.

## Overview

This tool sequentially scans DLsite product IDs, retrieves metadata for valid entries, and builds a comprehensive JSON database. It also downloads and organizes product images into a structured folder hierarchy.

## Features

- Asynchronous processing for efficient data collection
- Resumable operations with progress tracking
- Batch processing to manage memory usage
- Organized folder structure based on product ID ranges
- Automatic image downloading and management
- Periodic database saves to prevent data loss

## Requirements

- Python 3.7+
- Required packages:
  - asyncio
  - aiohttp
  - tqdm
  - dlsite_async

## Installation

1. Clone this repository
2. Install required dependencies:
   ```
   pip install aiohttp tqdm dlsite_async
   ```
3. Install the DlsiteAPI module (refer to the module's documentation)

## Usage

Run the script with:

```
python DLsite_DB_Scraper.py
```

The script will:
1. Check for existing progress and resume if available
2. Process RJ product IDs (doujin works) in the specified ranges
3. Process VJ product IDs (commercial works) in the specified ranges
4. Save results to `dlsite_database.json`

## Output

### Database Format

The output database is structured as follows:
```json
{
  "updated_at": "YYYY-MM-DD HH:MM:SS",
  "items": [
    {
      "maker": "Circle/Brand Name",
      "code": "RJ/VJ######",
      "title": "Product Title",
      "translate-title": "NaN"
    },
    ...
  ]
}
```

### Image Organization

Images are downloaded to:
```
DLsite_DB/[Base Folder]/[Product ID]/[Product ID]_img_main.jpg
```
where Base Folder groups products by 1000s (e.g., RJ001000, RJ002000).

## Notes

- The script filters for products from 'maniax' and 'pro' site categories
- Execution may take significant time depending on the ID ranges specified
- Progress is automatically saved and can be resumed if interrupted
- The script avoids unnecessary API calls for non-existent products
