import asyncio
import json
import re
import os
import math
import datetime
import aiohttp
from tqdm import tqdm
from dlsite_async import DlsiteAPI

# Set temporary file path
TEMP_FILE_PATH = os.path.join("DLsite_DB", ".temp")

# Function to save progress
def save_progress(current_id):
    os.makedirs("DLsite_DB", exist_ok=True)
    with open(TEMP_FILE_PATH, 'w') as f:
        f.write(f"{current_id}")
    print(f"\nProgress saved: ID {current_id}")

# Function to load progress
def load_progress():
    if os.path.exists(TEMP_FILE_PATH):
        try:
            with open(TEMP_FILE_PATH, 'r') as f:
                saved_id = f.read().strip()
                print(f"\nPrevious progress found: Starting from ID {saved_id}.")
                return saved_id
        except Exception as e:
            print(f"\nError reading .temp file: {e}")
    return None

# Function to extract ID number
def extract_number_and_type(id_str):
    code_type = id_str[:2]  # RJ or VJ

    if code_type in ["RJ", "VJ"]:
        number = int(id_str[2:])
        return number, code_type

    return 0, ""

def get_base_folder(product_id):
    # Extract the numeric part from formats like "RJ001305"
    match = re.match(r'([A-Z]+)(\d+)', product_id)
    if not match:
        return None

    prefix = match.group(1)  # "RJ" or "VJ"
    code_str = match.group(2)  # "001305"

    # Convert numeric part to integer
    code_num = int(code_str)

    # Round up to the nearest thousand
    base_num = math.ceil(code_num / 1000) * 1000

    # Format with the same length as the original code
    padding_length = len(code_str)
    formatted_base = str(base_num).zfill(padding_length)

    # Return new folder name
    return f"{prefix}{formatted_base}"

# Function to generate RJ ID from number
def generate_id(number, code_type):
    if code_type == "RJ":
        if 0 <= number <= 999999:  # 0 ~ 999999 → RJ000000 format
            return f"RJ{number:06d}"
        elif 1000000 <= number <= 9999999:  # 1000000 ~ 9999999 → RJ01000000 format
            return f"RJ{number:08d}"
    elif code_type == "VJ":
        if 0 <= number <= 999999:  # 0 ~ 999999 → VJ000000 format
            return f"VJ{number:06d}"
        elif 1000000 <= number <= 9999999:  # 1000000 ~ 9999999 → VJ01000000 format
            return f"VJ{number:08d}"

    return f"{code_type}{number}"  # Other exception cases

# Get work information
async def fetch_work_info(api, product_id):
    try:
        return await api.get_work(product_id)
    except Exception as e:
        # Don't print normal errors (many IDs won't exist)
        if "404" not in str(e):
            print(f"\nError while querying {product_id}: {e}")
        return None

# Fix image URL (add protocol)
def fix_image_url(url):
    if url and url.startswith('//'):
        return f"https:{url}"
    return url

# Download image
async def download_image(session, url, save_path):
    if not url:
        return False

    # Check if image already exists
    if os.path.exists(save_path):
        # Skip download if image already exists
        return True

    url = fix_image_url(url)
    try:
        async with session.get(url) as response:
            if response.status == 200:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(await response.read())
                return True
            else:
                print(f"\nImage download failed ({url}): {response.status}")
                return False
    except Exception as e:
        print(f"\nError during image download ({url}): {e}")
        return False

# Function to process specific ID range sequentially
async def process_sequential_ids(start_number, end_number, code_type, database, session):
    async with DlsiteAPI(locale="jp_JP") as api:
        # Process IDs sequentially
        for number in tqdm(range(start_number, end_number + 1), desc=f"Processing {code_type}"):
            product_id = generate_id(number, code_type)

            # Save progress periodically (every 10 items)
            if number % 10 == 0:
                save_progress(product_id)

            # Check if already in DB
            existing_entry = next((entry for entry in database if entry["code"] == product_id), None)

            if existing_entry:
                # Check image path
                base_folder = get_base_folder(product_id)
                save_dir = os.path.join("DLsite_DB", base_folder, product_id)
                image_filename = f"{product_id}_img_main.jpg"
                save_path = os.path.join(save_dir, image_filename)

                # Call API only if image doesn't exist
                if not os.path.exists(save_path):
                    work = await fetch_work_info(api, product_id)
                    if work and work.work_image:
                        await download_image(session, work.work_image, save_path)
            else:
                # Call API for new ID
                work = await fetch_work_info(api, product_id)

                # Process only items that meet the criteria
                if work and work.site_id in ['maniax', 'pro']:
                    # Determine maker based on RJ or VJ code
                    if work.product_id.startswith('RJ'):
                        maker = work.circle or "Unknown"
                    elif work.product_id.startswith('VJ'):
                        maker = work.brand or "Unknown"
                    else:
                        maker = "Unknown"

                    # Create entry with requested JSON structure
                    entry = {
                        "maker": maker,
                        "code": work.product_id,
                        "title": work.work_name,
                        "translate-title": "NaN"
                    }

                    # Save image
                    if work.work_image:
                        base_folder = get_base_folder(work.product_id)
                        save_dir = os.path.join("DLsite_DB", base_folder, work.product_id)
                        image_filename = f"{work.product_id}_img_main.jpg"
                        save_path = os.path.join(save_dir, image_filename)
                        await download_image(session, work.work_image, save_path)

                    database.append(entry)

            # Save database periodically (every 20 items)
            if number % 20 == 0:
                # Current update date
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Save results
                with open('dlsite_database.json', 'w', encoding='utf-8') as f:
                    json.dump({"updated_at": timestamp, "items": database}, f, ensure_ascii=False, indent=2)
                print(f"\nIntermediate save: {len(database)} items saved so far")

# Main function
async def main():
    # Check previously saved progress
    saved_id = load_progress()

    # Load previous database
    database = []
    if os.path.exists('dlsite_database.json'):
        try:
            with open('dlsite_database.json', 'r', encoding='utf-8') as f:
                db_data = json.load(f)
                if isinstance(db_data, dict) and "items" in db_data:
                    database = db_data["items"]
                else:
                    database = db_data
        except Exception as e:
            print(f"\nError loading existing database: {e}")

    # Define ranges to process
    rj_ranges = [
        (0, 499999),           # RJ000000 ~ RJ499999
        (1000000, 1369999)     # RJ01000000 ~ RJ01369999
    ]

    vj_range = [
        (0, 499999),           # VJ000000 ~ VJ499999
        (1000000, 1369999)     # VJ01000000 ~ VJ01369999
    ]
    # Set start information
    start_number = 0
    start_code_type = "RJ"
    rj_range_index = 0
    start_in_vj = False

    if saved_id:
        # Extract number and type from saved ID
        number, code_type = extract_number_and_type(saved_id)

        if code_type == "RJ":
            start_number = number
            start_code_type = "RJ"

            # Check which RJ range it belongs to
            if 0 <= number <= 499999:
                rj_range_index = 0
            elif 1000000 <= number <= 1369999:
                rj_range_index = 1

        elif code_type == "VJ":
            start_number = number
            start_code_type = "VJ"
            start_in_vj = True

        print(f"\nStarting from saved ID {saved_id}({code_type}) number {start_number}.")

    # Set batch size
    batch_size = 1000

    # Create HTTP session
    async with aiohttp.ClientSession() as session:
        # Process RJ codes if needed
        if not start_in_vj:
            # Process RJ ranges
            for i in range(rj_range_index, len(rj_ranges)):
                range_start, range_end = rj_ranges[i]

                # Continue from where we left off in the first range
                if i == rj_range_index:
                    current_start = start_number
                else:
                    current_start = range_start

                print(f"\nStarting to process RJ range {range_start}-{range_end} (start number: {current_start})")

                # Process in batches
                for batch_start in range(current_start, range_end + 1, batch_size):
                    batch_end = min(batch_start + batch_size - 1, range_end)
                    print(f"\nProcessing batch: {batch_start} ~ {batch_end}")
                    await process_sequential_ids(batch_start, batch_end, "RJ", database, session)

                    # Save after batch processing
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with open('dlsite_database.json', 'w', encoding='utf-8') as f:
                        json.dump({"updated_at": timestamp, "items": database}, f, ensure_ascii=False, indent=2)

                    print(f"\nCurrently {len(database)} items have been saved.")

        # Process VJ codes
        vj_start = start_number if start_in_vj else vj_range[0]
        vj_end = vj_range[1]

        print(f"\nStarting to process VJ range {vj_start}-{vj_end}")

        # Process in batches
        for batch_start in range(vj_start, vj_end + 1, batch_size):
            batch_end = min(batch_start + batch_size - 1, vj_end)
            print(f"\nProcessing batch: {batch_start} ~ {batch_end}")
            await process_sequential_ids(batch_start, batch_end, "VJ", database, session)

            # Save after batch processing
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open('dlsite_database.json', 'w', encoding='utf-8') as f:
                json.dump({"updated_at": timestamp, "items": database}, f, ensure_ascii=False, indent=2)

            print(f"\nCurrently {len(database)} items have been saved.")

    # Delete temporary file when all processing is complete
    if os.path.exists(TEMP_FILE_PATH):
        os.remove(TEMP_FILE_PATH)
        print("\nAll processing complete, .temp file deleted.")

    print("\n\nAll ID processing complete!")

# Execute script
if __name__ == "__main__":
    asyncio.run(main())