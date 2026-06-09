#!/usr/bin/env python3
"""
AdShare Enhanced Automation Script
Combines features from ad.py with improved symbol matching from adshare_solver_with_ten_backup.py
and fixed 10-parsing functionality.
"""
import os
import sys
import time
import requests
from bs4 import BeautifulSoup
import re
import adshare_login
import random
from datetime import datetime
import json

# ANSI color codes
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'

# Import the existing login functionality
from adshare_login import get_session, BASE_URL

# Define symbol types based on solver logic
SYMBOL_TYPES = {
    'CIRCLE': 'circle',
    'SQUARE': 'square',
    'DIAMOND': 'diamond',
    'ARROW_DOWN': 'arrow_down',
    'ARROW_LEFT': 'arrow_left',
    'BACKGROUND_CIRCLE': 'background_circle',
    'UNKNOWN': 'unknown'
}

def classify_symbol_type(element):
    """
    Classify symbol type based on SVG content or background image, following data.txt patterns
    """
    if element is None:
        return SYMBOL_TYPES['UNKNOWN']

    # Check if it's a background image element (like in JavaScript version)
    if hasattr(element, 'name') and element.name == 'div':
        style_attr = element.get('style', '')
        if 'background' in style_attr.lower() and ('img.gif' in style_attr.lower() or 'https://adsha.re/tex/img/img.gif' in style_attr.lower()):
            return SYMBOL_TYPES['BACKGROUND_CIRCLE']
    elif hasattr(element, 'find'):
        # Look for a child div with background image (for cases where we're checking an <a> tag)
        div = element.find('div')
        if div:
            style_attr = div.get('style', '')
            if 'background' in style_attr.lower() and ('img.gif' in style_attr.lower() or 'https://adsha.re/tex/img/img.gif' in style_attr.lower()):
                return SYMBOL_TYPES['BACKGROUND_CIRCLE']

    # Additional check: look for any div with background image inside this element
    if hasattr(element, 'find_all'):
        all_divs = element.find_all('div')
        for div in all_divs:
            style_attr = div.get('style', '')
            if 'background' in style_attr.lower() and ('img.gif' in style_attr.lower() or 'https://adsha.re/tex/img/img.gif' in style_attr.lower()):
                return SYMBOL_TYPES['BACKGROUND_CIRCLE']

    # Check if it's an SVG element
    svg_element = element if hasattr(element, 'name') and element.name == 'svg' else element.find('svg') if hasattr(element, 'find') else None
    if svg_element is None or not str(svg_element):
        return SYMBOL_TYPES['UNKNOWN']

    svg_content = str(svg_element).lower()

    # Use exact pattern matching based on data.txt
    # Downward Arrow (0deg rotation) - points="25 75 37.5 75 50 50 62.5 75 75 75 50 25 25 75"
    if ('rotate:0deg' in svg_content and 'polygon' in svg_content and
        '25 75 37.5 75 50 50 62.5 75 75 75 50 25 25 75' in svg_content):
        return SYMBOL_TYPES['ARROW_DOWN']

    # Upward Arrow (180deg rotation) - points="25 75 37.5 75 50 50 62.5 75 75 75 50 25 25 75"
    elif ('rotate:180deg' in svg_content and 'polygon' in svg_content and
          '25 75 37.5 75 50 50 62.5 75 75 75 50 25 25 75' in svg_content):
        return SYMBOL_TYPES['ARROW_DOWN']

    # Left-pointing Arrow - points="25 25 25 37.5 50 50 25 62.5 25 75 75 50 25 25"
    elif ('polygon' in svg_content and '25 25 25 37.5 50 50 25 62.5 25 75 75 50 25 25' in svg_content):
        return SYMBOL_TYPES['ARROW_LEFT']

    # Circle Pattern - concentric circles at cx="50" cy="50"
    elif 'circle' in svg_content and 'cx="50"' in svg_content and 'cy="50"' in svg_content:
        circles = svg_content.count('<circle')
        if circles >= 2:
            return SYMBOL_TYPES['CIRCLE']

    # Square Pattern - nested rectangles at x="25" y="25" and x="37.5" y="37.5"
    elif ('rect' in svg_content and 'x="25"' in svg_content and 'y="25"' in svg_content and
          'x="37.5"' in svg_content and 'y="37.5"' in svg_content):
        return SYMBOL_TYPES['SQUARE']

    # Diamond Pattern - rotated squares with transform matrix
    elif ('transform="matrix(0.7071' in svg_content and 'x="28.8"' in svg_content and
          'x="39.4"' in svg_content):
        return SYMBOL_TYPES['DIAMOND']

    # For any remaining arrow detection without rotation info
    elif 'polygon' in svg_content and '25 75 37.5 75 50 50 62.5 75 75 75 50 25 25 75' in svg_content:
        return SYMBOL_TYPES['ARROW_DOWN']

    return SYMBOL_TYPES['UNKNOWN']

def calculate_similarity(str1, str2):
    """Calculate string similarity for fuzzy matching (Levenshtein distance), following solver.js logic"""
    # Direct comparison like JavaScript version without extra preprocessing
    longer = str1 if len(str1) > len(str2) else str2
    shorter = str2 if len(str1) > len(str2) else str1

    if len(longer) == 0:
        return 1.0

    edit_distance = get_edit_distance(longer, shorter)
    similarity = (len(longer) - edit_distance) / float(len(longer))
    return similarity

def get_edit_distance(a, b):
    """Calculate the Levenshtein distance between two strings"""
    if len(a) == 0:
        return len(b)
    if len(b) == 0:
        return len(a)

    # Create a matrix of size (len(b)+1) x (len(a)+1)
    matrix = [[0 for _ in range(len(a) + 1)] for _ in range(len(b) + 1)]

    # Initialize first row and column
    for i in range(len(b) + 1):
        matrix[i][0] = i
    for j in range(len(a) + 1):
        matrix[0][j] = j

    # Fill the matrix
    for i in range(1, len(b) + 1):
        for j in range(1, len(a) + 1):
            if b[i-1] == a[j-1]:
                matrix[i][j] = matrix[i-1][j-1]
            else:
                matrix[i][j] = min(
                    matrix[i-1][j-1] + 1,  # substitution
                    matrix[i][j-1] + 1,    # insertion
                    matrix[i-1][j] + 1     # deletion
                )

    return matrix[len(b)][len(a)]

def solve_symbol_game(html_content):
    """
    Parse the HTML to find the question symbol and answer options,
    then determine the correct answer using solver.js logic
    """
    original_html_content = html_content  # Keep reference for low confidence saving
    soup = BeautifulSoup(html_content, 'html.parser')

    # Look for the timer.innerHTML assignment in JavaScript
    script_tags = soup.find_all('script')

    # Search for the timer element update in scripts
    timer_script_content = None
    for script in script_tags:
        if script.string and 'timer.innerHTML' in script.string:
            timer_script_content = script.string
            break

    # If we found the timer update script, extract the HTML content
    if timer_script_content:
        # Look for the timer.innerHTML assignment after counter=0
        # Updated regex to properly handle JavaScript string escaping
        import re

        # Look for the part where counter becomes 0 and the timer.innerHTML is set
        # This pattern looks for: counter = 0; ... timer.innerHTML = 'content'
        pattern = r'counter = 0;[^}]*timer\.innerHTML\s*=\s*([\'"])(.*?)(?<!\\)\1'
        matches = re.search(pattern, timer_script_content, re.DOTALL)

        if matches:
            # matches.group(1) is the quote character, matches.group(2) is the content
            dynamic_html = matches.group(2)

            # Handle JavaScript string escaping properly
            dynamic_html = dynamic_html.replace('\\"', '"').replace('\\/', '/')
            dynamic_html = dynamic_html.replace('\\\'', "'")
            dynamic_html = dynamic_html.replace('\\t', ' ').replace('\\n', ' ').replace('\\r', ' ')
            # Handle multiple levels of backslash escaping
            dynamic_html = dynamic_html.replace('\\\\', '\\')

            game_soup = BeautifulSoup(dynamic_html, 'html.parser')
        else:
            print("Could not find timer.innerHTML assignment after counter=0")
            # Look for any timer.innerHTML assignment using improved pattern
            any_pattern = r'timer\.innerHTML\s*=\s*([\'"])(.*?)(?<!\\)\1'
            pattern_matches = re.findall(any_pattern, timer_script_content, re.DOTALL)

            if pattern_matches:
                # Look for the one that contains game elements
                extracted = False
                for match in pattern_matches:
                    content = match[1]  # The content part of the match
                    if 'adsha.re' in content and ('<svg' in content or '<a' in content):
                        dynamic_html = content
                        dynamic_html = dynamic_html.replace('\\"', '"').replace('\\/', '/')
                        dynamic_html = dynamic_html.replace('\\\'', "'")
                        dynamic_html = dynamic_html.replace('\\t', ' ').replace('\\n', ' ').replace('\\r', ' ')
                        dynamic_html = dynamic_html.replace('\\\\', '\\')

                        game_soup = BeautifulSoup(dynamic_html, 'html.parser')
                        print("Extracted game elements from timer.innerHTML assignment with game content")
                        extracted = True
                        break

                if not extracted:
                    # Use the last match if no game content was found
                    dynamic_html = pattern_matches[-1][1]
                    dynamic_html = dynamic_html.replace('\\"', '"').replace('\\/', '/')
                    dynamic_html = dynamic_html.replace('\\\'', "'")
                    dynamic_html = dynamic_html.replace('\\t', ' ').replace('\\n', ' ').replace('\\r', ' ')
                    dynamic_html = dynamic_html.replace('\\\\', '\\')

                    game_soup = BeautifulSoup(dynamic_html, 'html.parser')
                    print("Extracted game elements from fallback timer.innerHTML assignment")
            else:
                print("Could not extract timer.innerHTML in any way, using fallback")
                # Fallback to the current page content
                game_soup = soup
    else:
        print("No script with timer.innerHTML found, using fallback")
        # Try to find the timer element in the static HTML
        timer_element = soup.find('div', id='timer')
        if timer_element:
            timer_html = str(timer_element)
            game_soup = BeautifulSoup(timer_html, 'html.parser')
        else:
            game_soup = soup  # fallback

    # Look for SVG elements and associated links in the game content
    # Use findAll to catch all occurrences
    svgs = game_soup.find_all('svg')
    links = game_soup.find_all('a', href=re.compile(r'adsha\.re|symbol-matching-game'))

    # If the standard parsing didn't find elements, try a more direct approach
    # from the actual output you showed me
    if len(svgs) == 0 or len(links) == 0:
        # The HTML might be too mangled for BeautifulSoup to parse properly
        # Let's try to extract directly from the JavaScript content
        if timer_script_content:
            import re
            # Extract the content from the timer.innerHTML assignment after counter = 0
            # Use the same improved regex pattern that worked in the extraction script
            content_pattern = r'counter = 0;[^}]*timer\.innerHTML\s*=\s*([\'"])(.*?)(?<!\\)\1'
            content_match = re.search(content_pattern, timer_script_content, re.DOTALL)

            raw_content = None
            if content_match:
                raw_content = content_match.group(2)
            else:
                # Try finding any timer.innerHTML assignment with game elements
                any_pattern = r'timer\.innerHTML\s*=\s*([\'"])(.*?)(?<!\\)\1'
                pattern_matches = re.findall(any_pattern, timer_script_content, re.DOTALL)

                for match in pattern_matches:
                    content = match[1]  # The content part of the match
                    if 'adsha.re' in content and ('<svg' in content or '<a' in content):
                        raw_content = content
                        break

                if raw_content is None and pattern_matches:
                    # Use the last match if no game content was found
                    raw_content = pattern_matches[-1][1]

            if raw_content:
                # Handle the JavaScript string escaping properly
                raw_content = raw_content.replace('\\"', '"').replace('\\/', '/').replace('\\\'', "'")
                raw_content = raw_content.replace('\\t', ' ').replace('\\n', ' ').replace('\\r', ' ')
                raw_content = raw_content.replace('\\\\', '\\')

                print("Processing raw_content for manual parsing...")

                # Find the question SVG (the one that's NOT in an <a> tag but in a div with href)
                # This pattern finds a div with href attribute (which is the question) containing an SVG
                question_div_pattern = r'(<div[^>]*href\s*=\s*["\'][^"\']*adsha\.re[^"\']*["\'][^>]*>.*?<svg[^>]*>.*?</svg>.*?</div>\s*</div>)'
                question_matches = re.findall(question_div_pattern, raw_content, re.DOTALL | re.IGNORECASE)

                if question_matches:
                    # Found the question element - process it
                    question_content = question_matches[0]
                    question_soup = BeautifulSoup(question_content, 'html.parser')
                    question_svgs = question_soup.find_all('svg')

                    if question_svgs:
                        # Use the first SVG as the question
                        svgs = [question_svgs[0]]
                        print(f"Found {len(question_svgs)} question SVG(s) manually")

                    # Now find all the answer links
                    # These are <a> tags containing SVGs or divs with background images
                    answer_link_pattern = r'(<a[^>]*href\s*=\s*["\'][^"\']*adsha\.re[^"\']*["\'][^>]*>.*?</a>)'
                    answer_matches = re.findall(answer_link_pattern, raw_content, re.DOTALL | re.IGNORECASE)

                    print(f"Found {len(answer_matches)} potential answer links with regex")

                    # Process each answer match
                    for answer_match in answer_matches:
                        answer_soup = BeautifulSoup(answer_match, 'html.parser')
                        answer_link = answer_soup.find('a')
                        if answer_link:
                            # Check if this link wasn't already added
                            link_href = answer_link.get('href')
                            link_exists = False
                            for existing_link in links:
                                if existing_link.get('href') == link_href:
                                    link_exists = True
                                    break

                            if not link_exists:
                                links.append(answer_link)

                print(f"After manual parsing: {len(svgs)} SVGs and {len(links)} links")

    # Identify the question element and answer elements from the game structure
    question_element = None
    answer_elements = []

    # Identify question and answer elements based on their href attributes and structure
    # The question is typically in a div with href (not directly in an <a> tag), while answers are in <a> tags
    for svg in svgs:
        # Find the closest parent that has an href attribute
        current = svg
        href_parent = None
        while current and current != (game_soup if 'game_soup' in locals() else soup):
            if current.get('href'):
                href_parent = current
                break
            current = current.parent

        if href_parent and href_parent.name == 'a':
            # This SVG is inside an <a> tag - it's an answer
            answer_elements.append((href_parent, svg))
        else:
            # Check if this SVG is in a div that has href (question structure)
            # Look for div parent with href
            current = svg
            div_with_href = None
            while current and current != (game_soup if 'game_soup' in locals() else soup):
                if current.name == 'div' and current.get('href'):
                    div_with_href = current
                    break
                current = current.parent

            if div_with_href:
                # This SVG is in a div with href - it's likely the question
                if question_element is None:
                    question_element = svg
            else:
                # If no clear parent with href, use the original logic as fallback
                parent = svg.parent
                is_in_link = False
                while parent and parent != (game_soup if 'game_soup' in locals() else soup):
                    if parent.name == 'a':
                        is_in_link = True
                        break
                    parent = parent.parent

                if not is_in_link and question_element is None:
                    question_element = svg
                elif is_in_link:
                    # Find the link that contains this SVG
                    parent = svg.parent
                    while parent and parent != (game_soup if 'game_soup' in locals() else soup):
                        if parent.name == 'a':
                            answer_elements.append((parent, svg))
                            break
                        parent = parent.parent

    # If no standalone SVG found, look for non-link elements that may contain the question
    if question_element is None:
        # Look for divs that might have background images (background circles)
        # Search for divs with background image containing img.gif
        all_divs = (game_soup if 'game_soup' in locals() else soup).find_all('div')
        for div in all_divs:
            style_attr = div.get('style', '')
            if 'background' in style_attr.lower() and ('img.gif' in style_attr.lower() or 'https://adsha.re/tex/img/img.gif' in style_attr.lower()):
                question_element = div
                break
    # If no question element found with the improved logic, fall back to original
    if question_element is None and svgs:
        question_element = svgs[0]  # Take the first SVG as the question

    # Check all links for answers (whether they contain SVGs or background image divs)
    for link in links:
        # Check for background images in the link first
        all_divs_in_link = link.find_all('div')
        for div in all_divs_in_link:
            style_attr = div.get('style', '')
            if 'background' in style_attr.lower() and ('img.gif' in style_attr.lower() or 'https://adsha.re/tex/img/img.gif' in style_attr.lower()):
                answer_elements.append((link, div))

        # Also check for SVGs in the same link
        link_svgs = link.find_all('svg')
        for svg in link_svgs:
            # Make sure this SVG element is not the question element
            is_question_svg = False
            if question_element and hasattr(question_element, 'name') and question_element.name == 'svg':
                # Simple check - if the string representations are the same, it's the question
                if str(svg) == str(question_element):
                    is_question_svg = True

            if not is_question_svg:
                answer_elements.append((link, svg))

    if question_element is None:
        return None

    if not answer_elements:
        return None

    # Classify the question element
    question_type = None
    question_content = ""

    if hasattr(question_element, 'name') and question_element.name == 'svg':
        question_svg = question_element
        question_type = classify_symbol_type(question_svg)

        
    else:
        # Question is a div with background image (background circle)
        question_type = SYMBOL_TYPES['BACKGROUND_CIRCLE']
        question_content = str(question_element)

    # Process each answer element
    answer_links = []
    answer_contents = []
    answer_types = []

    for i, (link, element) in enumerate(answer_elements):
        if hasattr(element, 'name') and element.name == 'svg':
            answer_type = classify_symbol_type(element)
        else:
            # Answer is a div with background image
            answer_type = classify_symbol_type(element)  # Use the function to classify properly

        answer_links.append(link)
        answer_contents.append(str(element))
        answer_types.append(answer_type)

    # Apply solver.js logic to find the best match
    best_match = None
    highest_confidence = 0
    exact_matches = []

    # Only show when we have a match with high confidence (>0.80)
    for i, (answer_type, answer_content, link) in enumerate(zip(answer_types, answer_contents, answer_links)):
        # Apply the same logic as in solver.js
        if question_type == SYMBOL_TYPES['CIRCLE'] and answer_type == SYMBOL_TYPES['BACKGROUND_CIRCLE']:
            # Circle to background circle match
            confidence = 0.98
            if confidence > highest_confidence:
                highest_confidence = confidence
                best_match = {
                    'index': i,
                    'confidence': confidence,
                    'exact': True,
                    'match_type': 'svg_to_background'
                }
        elif question_type == SYMBOL_TYPES['BACKGROUND_CIRCLE'] and answer_type == SYMBOL_TYPES['CIRCLE']:
            # Background circle to circle match
            confidence = 0.98
            if confidence > highest_confidence:
                highest_confidence = confidence
                best_match = {
                    'index': i,
                    'confidence': confidence,
                    'exact': True,
                    'match_type': 'background_to_svg'
                }
        elif question_type == SYMBOL_TYPES['BACKGROUND_CIRCLE'] and answer_type == SYMBOL_TYPES['BACKGROUND_CIRCLE']:
            # Background to background match
            confidence = 1.0
            exact_matches.append({
                'index': i,
                'confidence': confidence,
                'exact': True,
                'match_type': 'background_to_background'
            })
        elif question_type == answer_type:
            # Same symbol type match (e.g., square-square, circle-circle, etc.)
            # For same types, use content similarity as well
            similarity = calculate_similarity(str(question_element), answer_content)
            if similarity == 1.0:
                exact_matches.append({
                    'index': i,
                    'confidence': similarity,
                    'exact': True,
                    'match_type': 'same_type_exact'
                })
            elif similarity > highest_confidence:
                highest_confidence = similarity
                best_match = {
                    'index': i,
                    'confidence': similarity,
                    'exact': False,
                    'match_type': 'same_type_fuzzy'
                }
        else:
            # Different symbol types - use traditional matching
            similarity = calculate_similarity(str(question_element), answer_content)
            if similarity == 1.0:
                exact_matches.append({
                    'index': i,
                    'confidence': similarity,
                    'exact': True,
                    'match_type': 'svg_exact'
                })
            elif similarity > highest_confidence:
                highest_confidence = similarity
                best_match = {
                    'index': i,
                    'confidence': similarity,
                    'exact': False,
                    'match_type': 'svg_fuzzy'
                }

    # Return exact match if available
    if exact_matches:
        best_match = exact_matches[0]

    if best_match:
        # ONLY proceed if confidence is greater than 0.80
        if best_match['confidence'] < 0.80:
            print(f"{Colors.RED}Confidence ({best_match['confidence']:.2f}) is below 0.80 threshold, not proceeding with answer{Colors.RESET}")
            return None

        answer_index = best_match['index']
        selected_link = answer_links[answer_index]
        link_href = selected_link.get('href')

        # Map type codes to readable names for the selected answer
        type_names = {
            'circle': 'Circle',
            'square': 'Square',
            'diamond': 'Diamond',
            'arrow_down': 'Arrow',
            'arrow_left': 'Left-Arrow',
            'background_circle': 'Background Circle',
            'unknown': 'Unknown'
        }
        selected_answer_type = answer_types[answer_index]
        readable_answer_type = type_names.get(selected_answer_type, selected_answer_type)

        result = {
            'link': link_href,
            'index': answer_index,
            'confidence': best_match['confidence'],
            'exact_match': best_match['exact'],
            'total_answers': len(answer_links),
            'match_type': best_match.get('match_type', 'unknown'),
            'question_type': question_type,
            'selected_answer_type': selected_answer_type,  # Add readable answer type
            'readable_answer_name': readable_answer_type  # Add the readable name for display
        }

        return result
    else:
        print(f"{Colors.RED}No suitable match found with high confidence{Colors.RESET}")
        return None

def verify_answer(session, link):
    """
    Follow the selected link and verify if the answer was correct
    """
    if not link:
        return False, "No link"

    # Add retry logic for network requests
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            response = session.get(link, timeout=30)  # Increased timeout to handle slower connections
            response.raise_for_status()

            # Check the final URL to determine if answer was correct
            final_url = response.url
            response_text = response.text  # Save response text for debugging

            if 'surf' in final_url and 'exchange' not in final_url:
                return True, final_url
            elif 'exchange' in final_url or 'wrong' in response_text.lower() or 'incorrect' in response_text.lower():
                # Wrong answer detected - save the complete HTML to a file for debugging
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"wrong_answer_{timestamp}.html"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(response_text)
                print(f"  {Colors.RED}✗ Wrong answer! Complete HTML saved to {filename}{Colors.RESET}")
                return False, final_url
            else:
                # Check if the response contains any error/wrong indicators in the HTML
                if any(indicator in response_text.lower() for indicator in ['error', 'wrong', 'incorrect', 'failed']):
                    # Save the HTML for debugging
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"wrong_answer_{timestamp}.html"
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(response_text)
                    print(f"  {Colors.RED}✗ Wrong answer detected in response! Complete HTML saved to {filename}{Colors.RESET}")
                    return False, final_url
                return None, final_url

        except requests.exceptions.RequestException as e:
            retry_count += 1
            print(f"  {Colors.RED}✗ Network error (attempt {retry_count}/{max_retries}): {str(e)}{Colors.RESET}")

            if retry_count < max_retries:
                time.sleep(2)  # Wait before retry
            else:
                return False, str(e)

class AdShareAutomation:
    def __init__(self, username, password):
        self.session = get_session(username, password)
        if not self.session:
            raise Exception("Failed to establish session")

        # Configuration options
        self.show_pixel_changes = False  # Config to show/hide pixel change logs

        # Set the target at the start of the script
        print(f"{Colors.CYAN}Setting target for User #4194 at script start...{Colors.RESET}")
        self.current_target_value, self.target = self.check_ten_page_target(self.session, target_id="4194", target_increment=700)
        if self.target is not None:
            print(f"{Colors.GREEN}Target for User #4194 set: {self.target}{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}Could not set target for User #4194, will try again later{Colors.RESET}")

        self.previous_pixel = None
        self.total_credits = 0
        self.total_claims = 0
        self.start_time = datetime.now()  # Track start time
        self.last_target_check_time = datetime.now()  # Track last target check time
        self.cph_samples = []  # Store CPH samples for rolling average
        self.credit_events = []  # Store exact credit earning events with timestamps
        self.target_achieved = False  # Track if target has been achieved
        
        # Initial target check on startup
        if self.target is not None:
            print(f"{Colors.CYAN}[INITIAL TARGET CHECK] Target: {self.target}{Colors.RESET}")
            # We'll check the actual surf pages in the first cycle

    def calculate_cph(self):
        """Calculate credits per hour based on exact credit earning events"""
        if len(self.credit_events) == 0:
            return 0.0
        
        current_time = datetime.now()
        
        # Get the most recent event for comparison
        most_recent_event = max(self.credit_events, key=lambda x: x['timestamp'])
        
        # Calculate time difference in hours
        time_diff_hours = (current_time.timestamp() - most_recent_event['timestamp']) / 3600.0
        
        # If we have at least 2 events, calculate growth rate between them
        if len(self.credit_events) >= 2:
            # Sort events by timestamp
            sorted_events = sorted(self.credit_events, key=lambda x: x['timestamp'])
            # Get the last two events
            previous_event = sorted_events[-2]
            current_event = sorted_events[-1]
            
            time_diff = (current_event['timestamp'] - previous_event['timestamp']) / 3600.0
            credits_gained = current_event['credits'] - previous_event['credits']
            
            if credits_gained > 0 and time_diff > 0:
                current_cph = credits_gained / time_diff
            else:
                current_cph = 0.0
        else:
            current_cph = 0.0
        
        # Add to samples for rolling average (keep last 10 samples)
        self.cph_samples.append(current_cph)
        if len(self.cph_samples) > 10:
            self.cph_samples.pop(0)
        
        # Return rolling average
        return sum(self.cph_samples) / len(self.cph_samples)
    
    def record_credit_event(self, credits_earned):
        """Record a credit earning event with exact timestamp"""
        if credits_earned > 0:
            self.credit_events.append({
                'timestamp': datetime.now().timestamp(),
                'credits': self.total_credits  # Store cumulative total, not incremental
            })
            
            # Keep only events from last 2 hours to prevent memory buildup
            two_hours_ago = datetime.now().timestamp() - 7200
            self.credit_events = [event for event in self.credit_events if event['timestamp'] >= two_hours_ago]
    
    def display_stats(self):
        """Display current statistics including CPH"""
        cph = self.calculate_cph()
        runtime = datetime.now() - self.start_time
        
        # Format runtime
        hours, remainder = divmod(int(runtime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        runtime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        print(f"{Colors.MAGENTA}{'='*50}{Colors.RESET}")
        print(f"{Colors.CYAN}STATISTICS{Colors.RESET}")
        print(f"{Colors.CYAN}Runtime: {Colors.GREEN}{runtime_str}{Colors.RESET}")
        print(f"{Colors.CYAN}Total Credits: {Colors.GREEN}{self.total_credits}{Colors.RESET}")
        print(f"{Colors.CYAN}Total Claims: {Colors.GREEN}{self.total_claims}{Colors.RESET}")
        print(f"{Colors.CYAN}Credits Per Hour: {Colors.YELLOW}{cph:.1f}{Colors.RESET}")
        print(f"{Colors.MAGENTA}{'='*50}{Colors.RESET}")

    def get_progress_bar_value(self, html_content):
        """
        Extract progress bar pixel value from HTML content
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # Look for the dynamic progress bar value in timer.innerHTML content
        script_tags = soup.find_all('script')

        for script in script_tags:
            if script.string and 'timer.innerHTML' in script.string:
                # Look for the timer.innerHTML assignment after counter=0
                counter_zero_pattern = r'counter = 0;[^}]*timer\.innerHTML\s*=\s*([\'"])(.*?)(?<!\\)\1'
                match = re.search(counter_zero_pattern, script.string, re.DOTALL)

                if match:
                    dynamic_html = match.group(2)
                    # Handle JavaScript string escaping properly
                    dynamic_html = dynamic_html.replace('\\"', '"').replace('\\/', '/')
                    dynamic_html = dynamic_html.replace('\\\'', "'")
                    dynamic_html = dynamic_html.replace('\\t', ' ').replace('\\n', ' ').replace('\\r', ' ')
                    dynamic_html = dynamic_html.replace('\\\\', '\\')

                    # Now parse the dynamic HTML to find flash_bar1
                    dynamic_soup = BeautifulSoup(dynamic_html, 'html.parser')
                    flash_bar1 = dynamic_soup.find('div', id='flash_bar1')

                    if flash_bar1:
                        inner_bar = flash_bar1.find('div')
                        if inner_bar:
                            style = inner_bar.get('style', '')
                            width_match = re.search(r'width:\s*([0-9.]+)px', style)
                            if width_match:
                                return float(width_match.group(1)), dynamic_html

        # Alternative: Check for flash_bar1 in main HTML if it's visible
        flash_bar1_pattern = r'<div[^>]*id=[\'"]flash_bar1[\'"][^>]*>.*?</div>'
        flash_bar1_match = re.search(flash_bar1_pattern, html_content, re.DOTALL)
        if flash_bar1_match:
            width_match = re.search(r'width:\s*([0-9.]+)px', flash_bar1_match.group(0))
            if width_match:
                return float(width_match.group(1)), html_content

        return None, html_content

    def detect_overlays(self, html_content):
        """
        Detect active overlays in the HTML content
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        overlays = {}

        # Look for overlay elements by ID
        overlay_ids = ['bolt', 'fast', 'star']
        for overlay_id in overlay_ids:
            element = soup.find('a', id=overlay_id)
            if element:
                style = element.get('style', '')
                # Check if display is not none (meaning it's visible)
                if 'display:none' not in style and 'display: none' not in style:
                    overlays[overlay_id] = {
                        'visible': True,
                        'style': style,
                        'onclick': element.get('onclick', '')
                    }

        return overlays

    def get_overlay_functions(self, html_content):
        """
        Extract overlay function URLs from HTML
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        script_tags = soup.find_all('script')

        tap_functions = {}
        for script in script_tags:
            if script.string:
                tap_patterns = {
                    'bolt': r'tap_bolt.*?["\']([^"\']*game[^"\']*)["\']',
                    'fast': r'tap_fast.*?["\']([^"\']*game[^"\']*)["\']',
                    'star': r'tap_star.*?["\']([^"\']*game[^"\']*)["\']'
                }

                for func_name, pattern in tap_patterns.items():
                    match = re.search(pattern, script.string, re.DOTALL | re.IGNORECASE)
                    if match:
                        url = match.group(1)
                        if not url.startswith('http'):
                            url = BASE_URL + (url if url.startswith('/') else '/' + url)
                        tap_functions[func_name] = url

        return tap_functions

    def get_circles_and_claim(self, html_content):
        """
        Extract number of filled circles and check for claim availability
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # Count filled circles by looking for the specific game circle classes (circ1 to circ5)
        filled_circles = 0
        for i in range(1, 6):  # Check circ1 to circ5
            circle_element = soup.find('div', class_=f'circ{i}')
            if circle_element:
                filled_circles += 1

        # Check for claim button
        claim_button = soup.find('a', href=lambda x: x and '/game/claim/' in x)
        claim_available = claim_button is not None
        claim_url = claim_button.get('href') if claim_button else None

        # Extract credit information (gray text)
        credits_text = None
        gray_span = soup.find('span', style=lambda x: x and 'color:#C0C0C0' in x)
        if gray_span:
            credits_text = gray_span.get_text().strip()

        return filled_circles, claim_available, claim_url, credits_text

    def claim_reward(self, claim_url):
        """
        Claim the reward from the claim URL and extract reward information
        """
        if not claim_url:
            return False, "No claim URL provided", {}

        try:
            # Ensure claim URL has proper domain
            if not claim_url.startswith('http'):
                claim_url = BASE_URL + claim_url if claim_url.startswith('/') else f"{BASE_URL}/{claim_url}"

            response = self.session.get(claim_url, allow_redirects=True)

            if response.status_code == 200:
                # Parse the response to extract reward information
                soup = BeautifulSoup(response.text, 'html.parser')
                full_text = soup.get_text()

                reward_info = {}

                # Extract reward information
                # Look for "Congratulations! You won..." message to get the prize
                congrats_pattern = r'Congratulations!?\s+You won\s+(.*?)(?:\.|$)'
                congrats_match = re.search(congrats_pattern, full_text, re.IGNORECASE | re.DOTALL)

                if congrats_match:
                    prize_text = congrats_match.group(1).strip()  # Extract text after "You won"
                    prize_msg = f"Congratulations! You won {prize_text}"
                    reward_info['prize_message'] = prize_msg
                    print(f"{Colors.CYAN}Prize: {Colors.YELLOW}{prize_text}{Colors.RESET}")  # Show only the prize part
                elif 'Congratulations' in full_text:
                    # Fallback: find the complete congratulations message
                    congrats_start = full_text.find('Congratulations')
                    if congrats_start != -1:
                        # Look for the end of the congratulations message (next sentence)
                        end_pos = full_text.find('.', congrats_start)
                        if end_pos != -1:
                            prize_msg = full_text[congrats_start:end_pos+1]  # Include the period
                            reward_info['prize_message'] = prize_msg.strip()
                        else:
                            # If no period, look for exclamation mark or next line break
                            excl_pos = full_text.find('!', congrats_start)
                            if excl_pos != -1:
                                # Look for end of line or end of sentence
                                next_line = full_text.find('\n', excl_pos)
                                if next_line != -1:
                                    prize_msg = full_text[congrats_start:next_line]
                                else:
                                    prize_msg = full_text[congrats_start:excl_pos+1]
                                reward_info['prize_message'] = prize_msg.strip()

                # Extract credit amount
                credit_match = re.search(r'(\d+)\s*Traffic\s*Credits', full_text, re.IGNORECASE)
                if credit_match:
                    credits_won = int(credit_match.group(1))
                    reward_info['credits_won'] = credits_won
                    # Record exact credit earning event
                    self.record_credit_event(credits_won)
                    self.total_credits += credits_won

                # Extract any message div
                msg_div = soup.find('div', class_='msg')
                if msg_div:
                    reward_info['message'] = msg_div.get_text().strip()

                # Check for successful claim indicators
                success_indicators = ['Congratulations', 'won', 'You won', 'Claim successful']
                is_success = any(indicator in full_text for indicator in success_indicators)

                if is_success:
                    self.total_claims += 1
                    return True, "Claim successful", reward_info
                else:
                    return False, "Claim may not have been successful", reward_info
            else:
                return False, f"HTTP error: {response.status_code}", {}

        except requests.exceptions.RequestException as e:
            return False, f"Error claiming: {e}", {}

    def fetch_surf_page(self, min_delay=10, max_delay=11):
        """
        Fetch the surf page with a random delay
        """
        delay = random.uniform(min_delay, max_delay)  # Original 11-14 seconds to allow timer to complete
        surf_url = f"{BASE_URL}/surf"

        try:
            response = self.session.get(surf_url, timeout=30)
            response.raise_for_status()

            # Wait for a random delay to allow game elements to load with progress timer
            time.sleep(delay)

            # Fetch the page again to see the updated content
            response = self.session.get(surf_url, timeout=30)
            response.raise_for_status()

            return response.text
        except requests.exceptions.RequestException as e:
            return None

    def check_ten_page_target(self, session, target_id="4194", target_increment=700):
        """
        Check the current T (today's) value for a specific URL ID on the ten page and calculate target
        """
        from datetime import datetime

        ten_url = f"{BASE_URL}/ten"

        try:
            response = session.get(ten_url, timeout=30)
            response.raise_for_status()

            html_content = response.text

            current_value = None

            # Look for the T: (today) value for the specific ID in the HTML
            # Format is typically like: #4194 - some text T: 500
            # We need to make sure we capture the T: value that comes after the target_id, not the id itself
            pattern = rf'#\s*{re.escape(target_id)}[^T]*?T:\s*(\d+(?:,\d+)?)'
            match = re.search(pattern, html_content, re.DOTALL)

            if match:
                # Make sure the matched value is different from the target_id
                potential_value = int(match.group(1).replace(',', ''))
                if potential_value != int(target_id):
                    current_value = potential_value
                else:
                    match = None  # Reset match to try next approach

            if not match:
                # Alternative pattern - try to find the pattern in a different format
                alt_pattern = rf'#\s*{target_id}[^T]*?T:\s*(\d+(?:,\d+)?)'
                match = re.search(alt_pattern, html_content, re.DOTALL)

                if match:
                    # Again check if this value is different from target_id
                    potential_value = int(match.group(1).replace(',', ''))
                    if potential_value != int(target_id):
                        current_value = potential_value
                    else:
                        match = None  # Reset match to try next approach

            # If regex matching didn't work or gave wrong value, try line-by-line approach
            if current_value is None:
                lines = html_content.split('\n')
                for line in lines:
                    if f'#{target_id}' in line and 'T:' in line:
                        # Find all T: numbers in the line
                        t_pattern = r'T:\s*(\d+(?:,\d+)?)'
                        t_matches = re.findall(t_pattern, line)
                        for t_val in t_matches:
                            t_value = int(t_val.replace(',', ''))
                            if t_value != int(target_id):  # Make sure it's not the same as user ID
                                current_value = t_value
                                break
                        if current_value is not None:
                            break

            if current_value is not None:
                # Calculate today's target
                today = datetime.now().strftime("%Y-%m-%d")
                target = current_value + target_increment

                # Store target in file
                targets = {}
                try:
                    with open('ten_targets.json', 'r') as f:
                        targets = json.load(f)
                except FileNotFoundError:
                    pass

                key = f"{today}_{target_id}"
                targets[key] = target
                with open('ten_targets.json', 'w') as f:
                    json.dump(targets, f, indent=2)

                print(f"{Colors.MAGENTA}Target for User #{target_id}: T-value {current_value} + {target_increment} = {target}{Colors.RESET}")
                print(f"{Colors.MAGENTA}Time: {datetime.now().strftime('%H:%M:%S')}{Colors.RESET}")
                print(f"{Colors.MAGENTA}Current T-value (Today's Count): {current_value}{Colors.RESET}")

                return current_value, target
            else:
                print(f"{Colors.YELLOW}Could not find T-value for #{target_id} in the ten page{Colors.RESET}")
                return None, None

        except requests.exceptions.RequestException as e:
            print(f"{Colors.RED}Error fetching ten page: {e}{Colors.RESET}")
            return None, None

    def run_cycle(self):
        """
        Execute one complete automation cycle
        """
        # Fetch the surf page
        html_content = self.fetch_surf_page()
        if not html_content:
            return

        # Extract credit information with more specific regex
        # Look for pattern like ">22,831 Credits<" or ">22831 Credits<"
        # Using a more precise pattern to avoid matching extra characters
        credit_match = re.search(r'>\s*(\d{1,3}(?:,\d{3})*)\s*Credits?\s*<', html_content)
        if credit_match:
            credits_original = credit_match.group(1)  # Keep original format with commas
            credits_count = credits_original.replace(',', '')
            current_credits = int(credits_count)

            # Update the internal total credits tracker to match actual displayed credits
            credits_diff = current_credits - self.total_credits
            if credits_diff > 0:
                # Record exact credit earning event
                self.record_credit_event(credits_diff)
                self.total_credits = current_credits

            print(f"{Colors.CYAN}Credits: {Colors.GREEN}{credits_original}{Colors.RESET}")
        
        # Display CPH every 10 cycles or every 5 minutes
        if not hasattr(self, 'cycle_count'):
            self.cycle_count = 0
        self.cycle_count += 1
        
        if self.cycle_count % 10 == 0 or (datetime.now() - self.start_time).total_seconds() % 300 < 15:
            cph = self.calculate_cph()
            print(f"{Colors.YELLOW}CPH: {Colors.GREEN}{cph:.1f}{Colors.RESET}")

        # Extract surfed pages (gray text)
        gray_text_match = re.search(r'<span[^>]*style=[\'"][^\'"]*color:\s*#C0C0C0[^\'"]*[\'"][^>]*>\s*(\d+)\s*</span>', html_content)
        if gray_text_match:
            surfed_pages = int(gray_text_match.group(1))
            print(f"{Colors.CYAN}Surf pages: {Colors.YELLOW}{surfed_pages}{Colors.RESET}")

            # Check target on first run or every 30 minutes
            current_time = datetime.now()
            hours_since_last_check = (current_time - self.last_target_check_time).total_seconds() / 3600
            is_first_run = not hasattr(self, 'first_check_done')
            
            if is_first_run or hours_since_last_check >= 0.5:
                if is_first_run:
                    print(f"\n{Colors.CYAN}[INITIAL TARGET CHECK]{Colors.RESET}")
                    self.first_check_done = True
                else:
                    print(f"\n{Colors.CYAN}[TEN PAGE MONITOR] 30-minute target check...{Colors.RESET}")
                    
                current_value, target = self.check_ten_page_target(self.session, target_id="4194", target_increment=700)
                if target is not None:
                    self.current_target_value = current_value
                    self.target = target
                    print(f"{Colors.CYAN}Target check: surfed_pages={surfed_pages}, target={target}{Colors.RESET}")
                    
                    # Check if we should start solving (when surfed pages is less than target)
                    if surfed_pages < target:
                        if self.target_achieved:
                            print(f"{Colors.GREEN}{Colors.BOLD}TARGET BELOW THRESHOLD! Surf pages ({surfed_pages}) < Target ({target}){Colors.RESET}")
                            print(f"{Colors.YELLOW}Starting all functionality...{Colors.RESET}")
                        self.target_achieved = False
                        print(f"{Colors.CYAN}Solving enabled - Surf pages ({surfed_pages}) < Target ({target}){Colors.RESET}")
                    # Check if we should stop solving (when surf pages reach or exceed target)
                    elif surfed_pages >= target:
                        if not self.target_achieved:
                            print(f"{Colors.GREEN}{Colors.BOLD}TARGET REACHED! Surf pages ({surfed_pages}) >= Target ({target}){Colors.RESET}")
                            print(f"{Colors.YELLOW}All functionality will now pause until surf pages drop below threshold.{Colors.RESET}")
                        self.target_achieved = True
                        print(f"{Colors.CYAN}Solving paused - Surf pages ({surfed_pages}) >= Target ({target}){Colors.RESET}")
                        
                self.last_target_check_time = current_time  # Update last check time

        # Get progress bar pixel value and show changes
        pixel_value, _ = self.get_progress_bar_value(html_content)
        if pixel_value is not None and self.show_pixel_changes:
            if self.previous_pixel is not None:
                pixel_change = pixel_value - self.previous_pixel
                if pixel_change > 0:
                    print(f"{Colors.MAGENTA}Pixel: {Colors.CYAN}{pixel_value:.2f}px {Colors.GREEN}(+{pixel_change:.2f}px){Colors.RESET}")
                elif pixel_change < 0:
                    print(f"{Colors.MAGENTA}Pixel: {Colors.CYAN}{pixel_value:.2f}px {Colors.RED}({pixel_change:.2f}px){Colors.RESET}")
                else:
                    print(f"{Colors.MAGENTA}Pixel: {Colors.CYAN}{pixel_value:.2f}px {Colors.YELLOW}(no change){Colors.RESET}")
            else:
                print(f"{Colors.MAGENTA}Pixel: {Colors.CYAN}{pixel_value:.2f}px{Colors.RESET}")
            self.previous_pixel = pixel_value

        # Detect and handle overlays only if target is not achieved
        if not self.target_achieved:
            active_overlays = self.detect_overlays(html_content)
            print(f"{Colors.CYAN}Overlay detection: {len(active_overlays)} overlays found{Colors.RESET}")

            if active_overlays:
                print(f"{Colors.YELLOW}Overlays: {Colors.RED}{list(active_overlays.keys())}{Colors.RESET}")

                # Get overlay functions
                tap_functions = self.get_overlay_functions(html_content)

                # Execute each detected active overlay
                for overlay_name in active_overlays.keys():
                    if overlay_name in tap_functions:
                        function_url = tap_functions[overlay_name]

                        print(f"{Colors.YELLOW}Executing {overlay_name}{Colors.RESET} overlay...")
                        try:
                            # Execute the overlay function which redirects to game page
                            response = self.session.get(function_url, timeout=30)

                            if response.status_code != 200:
                                print(f"{Colors.RED}ERROR: Bad response status {response.status_code}{Colors.RESET}")
                                print("Stopping script due to error")
                                return

                            # On the game page, check circles and claim if available
                            filled_circles, claim_available, claim_url, credits_text = self.get_circles_and_claim(response.text)

                            if filled_circles > 5:
                                print(f"{Colors.RED}ERROR: Invalid circle count detected: {filled_circles}{Colors.RESET}")
                                print("Stopping script due to error")
                                return

                            print(f"{Colors.CYAN}Circles: {Colors.GREEN}{filled_circles}/5{Colors.RESET}")

                            if claim_available and claim_url:
                                print(f"{Colors.GREEN}Claim detected!{Colors.RESET} Attempting to claim...")
                                claim_success, claim_msg, reward_info = self.claim_reward(claim_url)
                                if claim_success:
                                    print(f"{Colors.GREEN}✓ Claim successful!{Colors.RESET}")
                                    # Print reward details
                                    if 'credits_won' in reward_info:
                                        print(f"{Colors.GREEN}+{reward_info['credits_won']}{Colors.RESET} Traffic Credits")
                                    # Prize message is already printed in the claim_reward function
                                    if 'message' in reward_info:
                                        print(f"{Colors.MAGENTA}Message: {Colors.WHITE}{reward_info['message']}{Colors.RESET}")
                                else:
                                    print(f"{Colors.RED}✗ Claim failed: {claim_msg}{Colors.RESET}")

                            # Wait a bit before processing next overlay
                            time.sleep(1)

                        except requests.exceptions.RequestException as e:
                            print(f"{Colors.RED}Error executing {overlay_name}: {e}{Colors.RESET}")
                            print("Stopping script due to error")
                            return
                    else:
                        print(f"{Colors.RED}No URL found for {overlay_name}{Colors.RESET} overlay")
                        print("Stopping script due to missing function URL")
                        return
            else:
                # No overlays detected, proceed with symbol solving
                print(f"{Colors.CYAN}No overlays - attempting to solve symbols...{Colors.RESET}")
                solution = solve_symbol_game(html_content)

                if solution:
                    print(f"{Colors.GREEN}Solution found! Confidence: {solution['confidence']:.2f}{Colors.RESET}")
                    # Wait only a short time (800ms to 1200ms) to simulate human symbol matching time
                    time.sleep(random.uniform(0.5, 0.8))
                    is_correct, final_url = verify_answer(self.session, solution['link'])

                    if is_correct is True:
                        print(f"{Colors.GREEN}✓ Answer correct!{Colors.RESET}")
                        # Wait 1-2 seconds after clicking answer
                        time.sleep(random.uniform(0.5, 1.5))
                    elif is_correct is False:
                        print(f"{Colors.RED}✗ Answer wrong{Colors.RESET}")
                        # Wait 1-2 seconds after failed answer
                        time.sleep(random.uniform(1, 2))
                    else:
                        print(f"{Colors.YELLOW}? Unknown result{Colors.RESET}")
                        # Wait 1-2 seconds for unknown result
                        time.sleep(random.uniform(1, 2))
                else:
                    print(f"{Colors.YELLOW}No solution found{Colors.RESET}")
                    # Add a short wait before next cycle when no solution is found
                    time.sleep(2)
        else:
            # No overlays detected
            if self.target_achieved:
                print(f"{Colors.YELLOW}Target achieved - all functionality paused{Colors.RESET}")
                time.sleep(random.uniform(2, 3))  # Wait before next cycle
            else:
                # Proceed with symbol solving using improved solver
                print(f"{Colors.CYAN}Attempting to solve symbols...{Colors.RESET}")
                solution = solve_symbol_game(html_content)

                if solution:
                    print(f"{Colors.GREEN}Solution found! Confidence: {solution['confidence']:.2f}{Colors.RESET}")
                    # Wait only a short time (800ms to 1200ms) to simulate human symbol matching time
                    time.sleep(random.uniform(0.5, 0.8))
                    is_correct, final_url = verify_answer(self.session, solution['link'])

                    if is_correct is True:
                        print(f"{Colors.GREEN}✓ Answer correct!{Colors.RESET}")
                        # Wait 1-2 seconds after clicking answer
                        time.sleep(random.uniform(0.5, 1.5))
                    elif is_correct is False:
                        print(f"{Colors.RED}✗ Answer wrong{Colors.RESET}")
                        # Wait 1-2 seconds after failed answer
                        time.sleep(random.uniform(1, 2))
                    else:
                        print(f"{Colors.YELLOW}? Unknown result{Colors.RESET}")
                        # Wait 1-2 seconds for unknown result
                        time.sleep(random.uniform(1, 2))
                else:
                    print(f"{Colors.YELLOW}No solution found{Colors.RESET}")
                    # Add a short wait before next cycle when no solution is found
                    time.sleep(2)

    def run(self):
        """
        Run the automation continuously
        """
        print(f"{Colors.GREEN}{Colors.BOLD}Starting AdShare Enhanced Automation...{Colors.RESET}")
        print(f"{Colors.CYAN}Press Ctrl+C to stop{Colors.RESET}")

        try:
            while True:
                self.run_cycle()

        except KeyboardInterrupt:
            print(f"\n\n{Colors.RED}Automation stopped by user{Colors.RESET}")
            cph = self.calculate_cph()
            print(f"{Colors.CYAN}Summary: {Colors.GREEN}{self.total_claims} claims{Colors.CYAN}, {Colors.GREEN}{self.total_credits} credits{Colors.CYAN}, {Colors.YELLOW}{cph:.1f} CPH{Colors.RESET}")

def main():
    username = os.environ.get("ADS_USERNAME")
    password = os.environ.get("ADS_PASSWORD")

    if not username or not password:
        print(f"{Colors.RED}ERROR: ADS_USERNAME and ADS_PASSWORD environment variables must be set{Colors.RESET}")
        sys.exit(1)

    try:
        automation = AdShareAutomation(username, password)
        automation.run()
    except Exception as e:
        print(f"{Colors.RED}Error starting automation: {e}{Colors.RESET}")

if __name__ == "__main__":
    main()
