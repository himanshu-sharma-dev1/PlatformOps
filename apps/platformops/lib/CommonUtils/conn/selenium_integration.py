''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : selenium_integration.py
* Description       : Scrapy Integration with Selenium
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 09-Jan-2025 		Harsh Soni		            Created.
*********************************************************************************************************************'''



from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from CommonUtils.logs.AppLogging import utils_logger
import os
import re
import time
from fpdf import FPDF

# Create a custom PDF class that supports UTF-8
class PDF(FPDF):
    def header(self):
        pass

    def footer(self):
        pass

    def add_utf8_text(self, text):
        self.set_font("Helvetica", size=12)
        self.multi_cell(0, 10, text.encode('latin-1', 'replace').decode('latin-1'))


def _extract_document_urls(url, tmp_dir):
    """Extract document URLs from the specified web page."""
    local_driver = None  # Use a local instance of the driver

    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        local_driver = webdriver.Chrome(options=chrome_options)

        local_driver.get(url)

        # Wait for all anchor elements to load on the page
        WebDriverWait(local_driver, 30).until(EC.presence_of_all_elements_located((By.TAG_NAME, "a")))

        open_all_dynamic_content(local_driver)
        time.sleep(10)
        anchors = local_driver.find_elements(By.TAG_NAME, "a")
        if not anchors:
            print("No <a> tags found. Waiting 3 more seconds and retrying...")
            time.sleep(10)
            anchors = local_driver.find_elements(By.TAG_NAME, "a")
            print(f"Found {len(anchors)} anchor tags after retry.")


        extracted_links = [anchor.get_attribute('href') for anchor in anchors if anchor.get_attribute('href')]

        utils_logger.debug(f'Extracted Links: {extracted_links}')

        file_name = save_html_content_as_pdf(tmp_dir,local_driver)
        # save_html_to_file(tmp_dir, local_driver)  # Pass local_driver
        utils_logger.debug("Saved Web Page as Txt File")

        # Filter PDF and TXT links
        filtered_pdf_links = [link for link in extracted_links if '.pdf' in link.lower() or '.txt' in link.lower()]

    except Exception as e:
        utils_logger.debug(f"Error while extracting links: {str(e)}")
        return [] , ""

    finally:
        if local_driver:  # Ensure the driver is quit properly
            local_driver.quit()

    return filtered_pdf_links , file_name

def open_all_dynamic_content(driver):
    """Dynamically open all modals, accordions, or dropdowns."""
    print("Open all Dynamic Content")
    try:
        # Find elements with IDs that likely control modals or accordions
        clickable_elements = driver.find_elements(By.XPATH, "//*[starts-with(@id, 'accordion-')]")
        for element in clickable_elements:
            try:
                element_id = element.get_attribute("id")
                if element_id:  # Interact with the element if it has an ID
                    driver.execute_script("document.getElementById(arguments[0]).click();", element_id)
                    utils_logger.debug(f"Clicked element with ID: {element_id}")

                    # Wait briefly for content to load dynamically
                    WebDriverWait(driver, 5).until(EC.presence_of_all_elements_located((By.TAG_NAME, "div")))

            except Exception as e:
                utils_logger.debug(f"Error clicking element: {str(e)}")

    except Exception as e:
        utils_logger.debug(f"Error finding dynamic content: {str(e)}")

def save_html_content_as_pdf(directory_name,driver):
    time.sleep(2)
    page_text = driver.find_element(By.TAG_NAME, "body").text
    try:
        header =  driver.find_element(By.TAG_NAME, "h1").text.strip()
    except:
        header = driver.title.strip()

    sanitized_header = "IktaraInternal" + re.sub(r"[\\/*?:\"<>|']", "", header).lower().replace(" ", "-")
    if not sanitized_header:
        sanitized_header = "untitled_page"

    if not os.path.exists(directory_name):
        os.makedirs(directory_name)

    file_path = os.path.join(directory_name, f"{sanitized_header}.pdf")

    cleaned_text = (page_text.replace('\u2019', "'").replace('\u2013', '-').replace('\u2014', '--'))

    pdf = PDF()
    pdf.add_page()
    pdf.add_utf8_text(cleaned_text)
    pdf.output(file_path)

    return f"{sanitized_header}.pdf"



# def save_html_to_file(directory_name,local_driver):
#     html_content = local_driver.page_source
#
#     try:
#         page_title = local_driver.title.strip()
#         sanitized_title = "".join(c for c in page_title if c.isalnum() or c in (' ', '-', '_')).strip()
#         sanitized_title = sanitized_title.lower().replace(' ','-')
#         if not sanitized_title:
#             sanitized_title = "untitled_page"
#     except Exception as e:
#         utils_logger.debug(f"Error extracting title: {str(e)}")
#         sanitized_title = "untitled_page"
#
#     if not os.path.exists(directory_name):
#         os.makedirs(directory_name)
#
#     file_path = os.path.join(directory_name, f'{sanitized_title}.html')
#
#     if os.path.exists(file_path):
#         unique_id = os.urandom(4).hex()
#         file_path = os.path.join(directory_name, f'{sanitized_title}_{unique_id}.html')
#
#
#     with open(file_path, 'w', encoding='utf-8') as file:
#         file.write(html_content)
#     utils_logger.debug(f"Saved HTML content to: {file_path}")





