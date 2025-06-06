import asyncio
from playwright.async_api import async_playwright
import requests
from datetime import datetime
import os
import re
import subprocess
import random
import sys

async def check_for_appointments_loop():
    # Create directories for logs and screenshots
    os.makedirs("./Logs", exist_ok=True)
    os.makedirs("./Screenshots", exist_ok=True)
    pause_file = "pause_signal.txt"
    limit_file = "limit_date.txt"
    limit_distance_file = "Limit_distance.txt"

    def read_limit_date():
        if os.path.exists(limit_file):
            with open(limit_file, "r") as f:
                content = f.read().strip()
                try:
                    parsed_date = datetime.strptime(content, "%b %d %Y")
                    print(f"📅 Loaded limit date: {parsed_date.strftime('%Y-%m-%d')}")
                    return parsed_date
                except ValueError:
                    print(f"⚠️ Invalid date format in {limit_file}. Expected 'Sep 03 2025'.")
        else:
            print(f"📅 No limit date file found.")
        return None

    def read_limit_distance():
        if os.path.exists(limit_distance_file):
            try:
                with open(limit_distance_file, "r") as f:
                    distance = int(f.read().strip())
                    print(f"📏 Loaded distance limit: {distance} miles")
                    return distance
            except ValueError:
                print("⚠️ Invalid mileage in Limit_distance.txt — must be a whole number.")
        else:
            print("📏 No limit distance file found.")
        return None

# ----  You will need to adjust the LAT/LONG.   Format is 35.1234 for both.  Use Google to find your home Lat/Long.

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=200)
        context = await browser.new_context(
            permissions=["geolocation"],
            geolocation={"latitude": 35.1234, "longitude": -79.1234},
            locale="en-US"
        )
        page = await context.new_page()

        await page.goto("https://skiptheline.ncdot.gov")
        await page.wait_for_selector('text=Make an Appointment', timeout=7500)
        await page.click('text=Make an Appointment')
        await page.wait_for_selector('text=Please select an appointment type', timeout=7500)

        for _ in range(20):
            tiles = await page.query_selector_all("div.QflowObjectItem.form-control")
            for tile in tiles:
                hover = await tile.query_selector(".hover-div")
                if not hover:
                    continue
                full_text = (await hover.inner_text()).strip()
                if "Teen Driver Level 2" in full_text:
                    print("✅ Found 'Teen Driver Level 2', clicking tile...")
                    await tile.scroll_into_view_if_needed()
                    await asyncio.sleep(0.3)
                    await tile.click()
                    break
            else:
                await page.mouse.wheel(0, 500)
                await asyncio.sleep(0.5)
                continue
            break

        await page.wait_for_selector('text=Select a Location', timeout=7500)

        refresh_count = 0
        while True:
            webhook_sent = False
            limit_date = read_limit_date()
            limit_distance = read_limit_distance()
            print("🔁 Beginning new appointment scan loop...")
            found_location = False
            seen_location_ids = set()
            location_info = []

            processed_ids = set()
            for i in range(20):
                location_tiles = await page.query_selector_all("div.QflowObjectItem.form-control")

                new_tiles_found = False
                for idx, loc in enumerate(location_tiles):
                    try:
                        loc_id = await loc.get_attribute("data-id")
                        if not loc_id or loc_id in processed_ids:
                            continue
                        processed_ids.add(loc_id)
                        new_tiles_found = True

                        hover = await loc.query_selector(".hover-div")
                        lines = []
                        mileage = "unk"

                        mileage_elem = await loc.query_selector(".Enabled-unit")
                        if mileage_elem:
                            mileage = (await mileage_elem.inner_text()).strip()

                        if hover:
                            lines = (await hover.inner_text()).strip().split("\n")
                        elif await loc.inner_text():
                            lines = (await loc.inner_text()).strip().split("\n")

                        label = lines[0].strip() if lines else "Unknown"

                        # Check mileage limit
                        if mileage != "unk":
                            try:
                                numeric_miles = float(re.sub(r"[^0-9.]", "", mileage))
                                if limit_distance and numeric_miles > limit_distance:
                                    print(f"🚫 Skipping {label} — {numeric_miles}mi exceeds limit of {limit_distance}mi.")
                                    continue
                            except ValueError:
                                print(f"⚠️ Could not parse mileage for {label}: '{mileage}'")

                        class_list = await loc.get_attribute("class") or ""
                        no_avail = await loc.query_selector(".No-Availability")

                        has_warning = False
                        if no_avail:
                            style = await no_avail.get_attribute("style")
                            if style is None or "none" not in style:
                                has_warning = True

                        is_clickable = "Active-Unit" in class_list and not has_warning

                        location_info.append({
                            "id": loc_id,
                            "label": label,
                            "mileage": mileage,
                            "clickable": is_clickable
                        })

                        if is_clickable:
                            print(f"[{idx + 1:03}] {label} | Mileage: {mileage} | Clickable: Yes")
                            with open("./Logs/Hit_log.txt", "a") as log_file:
                                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                log_file.write(f"[{timestamp}] {label} | Mileage: {mileage} | Clickable: Yes\n")

                    except Exception as e:
                        print(f"⚠️ Error preparing location: {e}")
                        continue

                if not new_tiles_found:
                    break

                await page.mouse.wheel(0, 500)
                await asyncio.sleep(0.5)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            scroll_summary = f"[{timestamp}] ✅ Scroll complete. Found {len(location_info)} candidate tiles (clickable + non-clickable)."
            print(scroll_summary)
            with open("./Logs/Scan_log.txt", "a") as scan_log:
                scan_log.write(scroll_summary + "\n")

            for loc in location_info:
                if not loc['clickable'] or loc['id'] in seen_location_ids:
                    continue
                just_skipped = False
                seen_location_ids.add(loc['id'])
                label = loc['label']
                mileage = loc['mileage']

                print(f"🔍 Checking {label}...")
                try:
                    refreshed_tiles = await page.query_selector_all("div.QflowObjectItem.form-control")
                    target_tile = None
                    for tile in refreshed_tiles:
                        this_id = await tile.get_attribute("data-id")
                        if this_id == loc['id']:
                            target_tile = tile
                            break

                    if not target_tile:
                        print(f"⚠️ Tile with data-id {loc['id']} for {label} not found on re-check. Skipping.")
                        continue
                    await target_tile.scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)
                    
                    try:
                        await target_tile.click(force=True)
                        await page.wait_for_selector('text=Please select date and time.', timeout=20000)
                    except Exception as e:
                        print(f"⚠️ {label}: appointment page did not load after click — {e}")
                        await page.screenshot(path=f"./Screenshots/{label}_click_failed.png")
                        await page.go_back()
                        await page.wait_for_selector('text=Select a Location', timeout=7500)
                        await page.wait_for_load_state('networkidle')
                        continue
                
                    await asyncio.sleep(1)

                    time_select = await page.query_selector("select")
                    if not time_select:
                        print(f"🕳️ No time select found for {label} — likely ghost page.")
                        await page.go_back()
                        await page.wait_for_selector('text=Select a Location', timeout=7500)
                        await page.wait_for_load_state('networkidle')
                        continue

                    is_disabled = await time_select.get_attribute("disabled")
                    if is_disabled is not None:
                        print(f"🕳️ Time select is disabled at {label} — likely a non-bookable ghost slot.")
                        await page.go_back()
                        await page.wait_for_selector('text=Select a Location', timeout=10000)
                        await page.wait_for_load_state('networkidle')
                        continue


                    options = await time_select.query_selector_all("option")
                    valid_times = []
                    for idx, opt in enumerate(options):
                        time_label = (await opt.inner_text()).strip()
                        if time_label and time_label != "-":
                            valid_times.append(time_label)

                    if not valid_times:
                        print(f"🕳️ No valid appointment times at {label}.")
                        await page.go_back()
                        await page.wait_for_selector('text=Select a Location', timeout=20000)
                        await page.wait_for_load_state('networkidle')
                        continue

                    appointment_time = valid_times[0]
                    print(f"🎉 Appointment available at {label}: {appointment_time}")

                    next_btn = await page.query_selector("input.next-button[type='submit'][value='Next']")
                    if next_btn:
                        await next_btn.click()
                    try:
                        await page.wait_for_selector("label.displaydata-label:text('Time')", timeout=10000)
                    except Exception as e:
                        print(f"⚠️ Summary section did not appear after Next — {e}")
                        await page.screenshot(path=f"./Screenshots/{label}_summary_timeout.png")
                    # Find the label for "Time"
                    label_el = await page.query_selector("label.displaydata-label:text('Time')")
                    if label_el:
                        time_value_el = await label_el.evaluate_handle("label => label.parentElement.querySelector('.displaydata-text div')")
                        appointment_datetime_str = await time_value_el.inner_text() if time_value_el else None

                    else:
                        # Fallback to extracting from summary block if label lookup failed
                        summary_block = await page.query_selector("div#summary")  # or broader container
                        if summary_block:
                            summary_text = await summary_block.inner_text()
                            match = re.search(
                                r"(Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)\\s+"
                                r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
                                r"Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\\s+"
                                r"\\d{1,2}(?:st|nd|rd|th)?,?\\s+(?:at\\s+)?\\d{1,2}:\\d{2}\\s+[AP]M",
                                summary_text
                            )
                            if match:
                                appointment_datetime_str = match.group(0)
                            else:
                                appointment_datetime_str = None
                        else:
                            appointment_datetime_str = None


                    
                    parsed_time = None
                    if appointment_datetime_str:
                        try:
                            # Assume current year if year not present in string
                            appointment_datetime_str_with_year = f"{appointment_datetime_str}, {datetime.now().year}"
                            parsed_time = datetime.strptime(appointment_datetime_str_with_year, "%a %b %d, %I:%M %p, %Y")
                        except Exception as e:
                            print(f"⚠️ Could not parse appointment datetime: '{appointment_datetime_str}' — {e}")
                    else:
                        print("⚠️ Time label or value not found in confirmation page.")                    

                    print(f"🧾 Summary datetime text: {appointment_datetime_str}")

                    if limit_date and parsed_time and parsed_time > limit_date:
                        print(f"🚫 Skipping {label} — appointment {parsed_time} exceeds limit {limit_date}.")
                        with open(pause_file, "w") as f:
                            f.write("skip")
                        await page.go_back()
                        await page.wait_for_selector('text=Please select date and time.', timeout=20000)
                        await page.wait_for_load_state('networkidle')
                        await page.go_back()
                        await page.wait_for_selector('text=Select a Location', timeout=20000)
                        await page.wait_for_load_state('networkidle')
                        continue
                    
                    just_skipped = True

                    found_location = True
                    candidate_msg = f"{label} - {mileage} - " + (
                        parsed_time.strftime('%b %d, %I:%M %p') if parsed_time
                        else (appointment_datetime_str or appointment_time)
                    )

# ------ THis is where I push a message to my home assistant instance. If you have different webhook, you will have to
# -------adjust the JSON accordingly.

#                    if not webhook_sent:
#                        requests.post("http://xxx.yyy.zzz.www:8123/api/webhook/dmv_appointment_found", json={"message": candidate_msg})
#                        webhook_sent = True

                    if parsed_time:
                        subprocess.run([
                            "osascript", "-e",
                            f'display dialog "Appointment at {label} - {mileage} — {parsed_time.strftime('%b %d, %I:%M %p')}" with title "🚗 DMV Appointment Found" buttons ["OK"] default button "OK" giving up after 10'
                        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        print("⚠️ Skipping notification — could not parse appointment datetime.")

                    print("⏸️ Pausing 3 minutes for human interaction...")
                    pause_seconds = 180
                    open(pause_file, "w").close()

                    remaining = pause_seconds
                    while remaining > 0:
                        if os.path.exists(pause_file):
                            with open(pause_file, "r") as f:
                                command = f.read().strip().lower()

                            if command == "skip":
                                print("⏭️ Pause skipped by user command.")
                                open(pause_file, "w").close()
                                break
                            elif command == "extend":
                                print("⏱️ Pause extended by 2 minutes.")
                                remaining += 120
                                open(pause_file, "w").close()


                        print(f"\r⏳ Pausing for {remaining:3d} seconds...", end='', flush=True)
                        await asyncio.sleep(1)
                        remaining -= 1

                    print()

                    print("🔙 Resuming check — returning to location list.")
                    await page.go_back()
                    await page.wait_for_selector('text=Please select date and time.', timeout=20000)
                    await page.wait_for_load_state('networkidle')
                    await page.go_back()
                    await page.wait_for_selector('text=Select a Location', timeout=20000)
                    await page.wait_for_load_state('networkidle')
                    if just_skipped:
                        continue  # skip error logging after expected back-navigation
              
                except Exception as e:
                    print(f"❌ Error checking {label}: {e}")
                    if not just_skipped:
                        try:
                            await page.go_back()
                            await page.wait_for_selector('text=Select a Location', timeout=5000)
                        except:
                            print("⚠️ Could not navigate back after error")
                continue

            if not found_location:
                refresh_count += 1
                if refresh_count >= 60:
                    exit_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🛑 Reached {refresh_count} refreshes — exiting for cooldown."
                    print(exit_msg)
                    with open("./Logs/Scan_log.txt", "a") as scan_log:
                        scan_log.write(exit_msg + "\n")
                    break

                wait_time = random.randint(20, 30)
                print(f"⏳ Sleeping for {wait_time} seconds:", end='', flush=True)
                for remaining in range(wait_time, 0, -1):
                    sys.stdout.write(f"\r⏳ Sleeping for {remaining:3d} seconds...")
                    sys.stdout.flush()
                    await asyncio.sleep(1)
                print()
                print("🔄 Refreshing the page now...")
                await page.reload()
                print("✅ Page reloaded. Skipping confirmation dialog check.")

                print("⏳ Waiting for tiles to repopulate...")
                await page.wait_for_selector("div.QflowObjectItem.form-control", timeout=20000)

                tiles_ready = False
                for _ in range(10):
                    tiles = await page.query_selector_all("div.QflowObjectItem.form-control")
                    print(f"🔍 Checking tile count after reload: {len(tiles)}")
                    if len(tiles) > 50:
                        tiles_ready = True
                        break
                    await asyncio.sleep(0.5)

                if not tiles_ready:
                    print("⚠️ Warning: tiles did not repopulate as expected after reload.")

if __name__ == "__main__":
    try:
        asyncio.run(check_for_appointments_loop())
    except KeyboardInterrupt:
        print("\n⚠️ Script interrupted by user")
    except Exception as e:
        print(f"❌ Script failed with error: {e}")

