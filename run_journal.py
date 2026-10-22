import time
import re
import random
from playwright.sync_api import sync_playwright

def automate_all_students(page, keywords, processed_students):
    print("\nScanning page for student names...")

    all_text = page.locator("span, div").all_inner_texts()
    student_pattern = re.compile(r"^[А-Я][а-я]+ [А-Я][а-я]+$")

    student_names = []
    skipped_count = 0

    for text in all_text:
        text = text.strip()
        is_interface_subject = any(kw.lower() in text.lower() for kw in keywords)

        if student_pattern.match(text) and not is_interface_subject:
            if text not in student_names:
                # DEDUPLICATION CHECK: Skip if processed in any previous journal
                if text in processed_students:
                    skipped_count += 1
                    continue
                student_names.append(text)

    if skipped_count > 0:
        print(f"   [Notice] Automatically bypassing {skipped_count} students already evaluated in earlier journals.")

    print(f"Success! Found {len(student_names)} new students to process.")
    if not student_names:
        return True

    for name in student_names:
        try:
            print(f"Processing: {name}")
            page.get_by_text(name).first.click(force=True)
            page.wait_for_timeout(random.randint(350, 500))

            eval_button = page.locator("button:has-text('оценить учебные умения')")
            if eval_button.is_visible():
                eval_button.click()
                page.wait_for_timeout(random.randint(450, 600))
            else:
                close_btn = page.get_by_role("button", name="Закрыть", exact=True)
                if close_btn.is_visible():
                    close_btn.click()
                # Even if we can't evaluate them here, mark them so we don't get stuck on them
                processed_students.add(name)
                continue

            # --- RANDOMIZED TARGETED QUESTION FILLING ---
            print("   Answering rows organically...")
            question_rows = page.locator("div:has(> label:has-text('Часто'))").all()
            if not question_rows:
                question_rows = page.locator(".CZtlm_DGpYLNIT_tqZuO").all()

            for row in question_rows:
                try:
                    labels = row.locator("label")
                    if labels.count() >= 4:
                        random_answer = random.choice([2, 2, 2, 3, 3, 4])
                        labels.nth(random_answer).click(force=True, position={"x": 5, "y": 5})
                        page.wait_for_timeout(random.randint(50, 120))
                except:
                    pass

            page.wait_for_timeout(150)

            # --- THE "WAKE UP" LOOP ---
            save_button = page.get_by_role("button", name="Сохранить")
            if question_rows:
                try:
                    last_row_labels = question_rows[-1].locator("label")
                    if last_row_labels.count() >= 4:
                        for attempt in range(6):
                            if save_button.is_enabled():
                                break
                            last_row_labels.nth(2).click(force=True, position={"x": 5, "y": 5})
                            woke_up = False
                            for _ in range(8):
                                if save_button.is_enabled():
                                    woke_up = True
                                    break
                                page.wait_for_timeout(30)
                            if woke_up: break

                            last_row_labels.nth(3).click(force=True, position={"x": 5, "y": 5})
                            for _ in range(8):
                                if save_button.is_enabled():
                                    woke_up = True
                                    break
                                page.wait_for_timeout(30)
                            if woke_up: break
                except Exception:
                    pass

            # --- SAVE AND EXIT ---
            print("   Saving evaluation changes...")
            try:
                save_button.evaluate("node => node.removeAttribute('disabled')")
                page.wait_for_timeout(50)
                save_button.click(force=True)
            except:
                try: save_button.dispatch_event("click")
                except: pass

            page.wait_for_timeout(random.randint(400, 600))
            page.get_by_role("button", name="Закрыть", exact=True).click()
            page.wait_for_timeout(250)

            # SUCCESS: Add to session tracking registry
            processed_students.add(name)

        except Exception as e:
            print(f"   Skipped {name}: {e}")
            try: page.get_by_role("button", name="Закрыть", exact=True).click()
            except: page.keyboard.press("Escape")
            continue
    return True

def try_switch_to_next_journal(page, target_index, keywords):
    print(f"\nAttempting rapid hop to journal menu index [{target_index}] checking target keywords...")
    try:
        dropdown_candidates = page.locator("span.DSXOGdoSiFGKohRuaDDx").all()
        dropdown_trigger = None
        
        for candidate in dropdown_candidates:
            try:
                text = candidate.inner_text().strip()
                if any(kw.lower() in text.lower() for kw in keywords) or any(char.isdigit() for char in text):
                    dropdown_trigger = candidate
                    break
            except:
                pass

        if not dropdown_trigger:
            print("   [Error] Could not locate the Journal Selector UI element.")
            return False

        dropdown_trigger.click()
        page.wait_for_timeout(500) 

        raw_options = page.locator("span, li, [role='option']").all()
        menu_items = []
        seen_texts = set()

        for option in raw_options:
            try:
                if option.is_visible():
                    txt = option.inner_text().strip()
                    
                    class_attr = option.evaluate("node => node.className") or ""
                    if "DSXOGdoSiFGKohRuaDDx" in class_attr:
                        continue
                    
                    if txt and any(kw.lower() in txt.lower() for kw in keywords):
                        if txt not in seen_texts:
                            menu_items.append(option)
                            seen_texts.add(txt)
            except:
                pass

        if not menu_items:
            print(f"   [Error] No menu choices found matching your keywords.")
            return False

        if target_index >= len(menu_items):
            print("\n🎉 All available matching journal groups have been successfully processed!")
            return False

        next_journal_element = menu_items[target_index]
        try:
            print(f"   Advancing straight to option: '{next_journal_element.inner_text().strip()}'")
        except:
            print(f"   Advancing straight to menu slot {target_index + 1}...")

        next_journal_element.click(force=True)
        
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1800) 
        return True

    except Exception as e:
        print(f"   Rapid navigation encountered an issue: {e}")
        return False

def main():
    with sync_playwright() as p:
        print("Connecting to live Chrome window...")
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        default_context = browser.contexts[0]
        page = default_context.pages[0]
        
        # # Enable interceptor to record API responses with student marks
        # setup_network_interceptor(page)
        
        print(f"Connected to tab: '{page.title()}'")
        
        print("\n--- MULTI-KEYWORD SHARING CONFIGURATION ---")
        print("You can list multiple targets separated by commas.")
        raw_input = input("Enter subject keywords [Default: Информатика]: ").strip()
        
        if not raw_input:
            keywords = ["информатика"]
        else:
            keywords = [k.strip() for k in raw_input.split(",") if k.strip()]
            
        print(f"Active monitoring filter keywords: {keywords}")
        
        # Initialize session storage tracking across all sequential class journals
        processed_students = set()
        
        while True:
            user_input = input(f"\n--> Navigate to your first journal tab, then press [Enter] to start (or 'q' to quit): ")
            if user_input.lower() == 'q':
                break
            
            current_journal_idx = 0
            
            while True:
                # Pass the evaluation tracker set down into the runner routine
                finished = automate_all_students(page, keywords, processed_students)
                
                if finished:
                    print(f"\nCurrent class group processed completely. Total unique students processed so far: {len(processed_students)}")
                    current_journal_idx += 1
                    success = try_switch_to_next_journal(page, current_journal_idx, keywords)
                    
                    if not success:
                        print("Auto-advance paused.")
                        next_step = input("Press [Enter] to manually verify and process current page context, or 'q' to quit: ")
                        if next_step.lower() == 'q':
                            break
                    else:
                        print("Successfully loaded next journal view! Moving immediately to student array...")
                else:
                    break

if __name__ == "__main__":
    main()