#!/usr/bin/env python3
"""
HTML Quiz Parser - Extracts quiz questions from HTML and converts to JSON format

This script automatically installs required dependencies (beautifulsoup4) if not present.
No manual dependency installation required!

Usage: python3 html_to_json_parser.py <html_file_path>
Example: python3 html_to_json_parser.py assets/html/checkpoint1.html
"""

import re
import json
import sys
import subprocess
from pathlib import Path
import html

# Auto-install dependencies
def install_dependencies():
    """Install required dependencies if not available"""
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup
    except ImportError:
        print("BeautifulSoup4 not found. Installing...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'beautifulsoup4'])
            print("Successfully installed beautifulsoup4")
            from bs4 import BeautifulSoup
            return BeautifulSoup
        except subprocess.CalledProcessError:
            print("Failed to install beautifulsoup4. Please install manually with:")
            print("pip install beautifulsoup4")
            sys.exit(1)
        except ImportError:
            print("Error: Could not import BeautifulSoup4 after installation.")
            print("Please install manually with: pip install beautifulsoup4")
            sys.exit(1)

# Install dependencies and get BeautifulSoup
BeautifulSoup = install_dependencies()

def clean_text(text):
    """Clean HTML entities and extra whitespace from text"""
    if not text:
        return ""
    # Decode HTML entities
    text = html.unescape(text)
    # Remove extra whitespace and newlines
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_quiz_data(html_content):
    """Extract quiz questions, choices, and answers from HTML content"""
    soup = BeautifulSoup(html_content, 'html.parser')
    questions = []
    
    # Find all question paragraphs that start with a number
    question_pattern = re.compile(r'^\d+\.\s+')
    
    # Get all paragraphs first, then look for standalone strong/b tags that aren't in paragraphs
    all_paragraphs = soup.find_all('p')
    standalone_tags = []
    
    # Find standalone strong/b tags that are not inside paragraphs
    # Also find tags that are in malformed paragraphs (like question 5 in checkpoint1)
    for tag in soup.find_all(['strong', 'b']):
        tag_text = tag.get_text().strip()
        if question_pattern.match(tag_text):
            parent = tag.find_parent('p')
            if not parent:
                # Truly standalone tag
                standalone_tags.append(tag)
            elif parent and len(parent.find_all(['strong', 'b'])) > 1:
                # This might be a malformed case where multiple strong tags are in one paragraph
                # Check if this is a question number tag (like "5. ") followed by question text
                siblings = parent.find_all(['strong', 'b'])
                for i, sibling in enumerate(siblings):
                    sibling_text = sibling.get_text().strip()
                    # Check if this is a question number (like "5. " or "18. ")
                    if re.match(r'^\d+\.\s*$', sibling_text) and i + 1 < len(siblings):
                        # Check if the next sibling contains question text
                        next_sibling = siblings[i + 1]
                        if tag == sibling:
                            # This is the question number tag, treat as standalone
                            standalone_tags.append(tag)
                            break
    
    # Combine paragraphs and standalone tags
    all_elements = all_paragraphs + standalone_tags
    
    i = 0
    while i < len(all_elements):
        element = all_elements[i]
        question_tag = None
        
        if element.name == 'p':
            # Look for both <strong> and <b> tags within paragraphs
            question_tag = element.find('strong') or element.find('b')
        elif element.name in ['strong', 'b']:
            # This is a standalone strong/b tag
            question_tag = element
        
        # Check if this is a question (either full question or just question number)
        question_tag_text = question_tag.get_text().strip() if question_tag else ""
        is_question = False
        
        if question_tag and (question_pattern.match(question_tag_text) or re.match(r'^\d+\.\s*$', question_tag_text)):
            is_question = True
        
        if is_question:
            question_data = {}
            
            # Extract question text
            question_text = clean_text(question_tag.get_text())
            question_data['question'] = question_text
            
            # Check if there's an image associated with this question
            # Look for image in the current element or nearby elements
            img_found = False
            
            # Check current element for image (if it's a paragraph)
            if element.name == 'p':
                img_tag = element.find('img')
                if img_tag and img_tag.get('src'):
                    question_data['img'] = img_tag.get('src')
                    img_found = True
            
            # If no image found, check the next few elements
            if not img_found:
                for j in range(i + 1, min(i + 3, len(all_elements))):
                    next_element = all_elements[j]
                    if next_element.name == 'p':
                        img_tag = next_element.find('img')
                        if img_tag and img_tag.get('src'):
                            question_data['img'] = img_tag.get('src')
                            break
            
            # Find the next ul element that contains the choices
            # For complex questions, we need to look further ahead
            current_element = element.find_next_sibling()
            choices = []
            correct_answers = []
            question_parts = [question_text]  # Store all parts of the question
            pre_content = None  # Store any <pre> tag content
            
            while current_element:
                if current_element.name == 'ul':
                    # Found the choices list
                    li_elements = current_element.find_all('li')
                    
                    for li in li_elements:
                        # Extract choice text (remove HTML tags but keep content)
                        choice_text = clean_text(li.get_text())
                        if choice_text:  # Only add non-empty choices
                            choices.append(choice_text)
                            
                            # Check if this is a correct answer
                            # Look for any span or strong tag with color styling (any color means it's the answer)
                            colored_tag = li.find(['span', 'strong'], style=lambda x: x and 'color:' in x)
                            if colored_tag:
                                correct_answers.append(choice_text)
                            # Also check if the li element itself has the 'correct_answer' class
                            elif li.get('class') and 'correct_answer' in li.get('class'):
                                correct_answers.append(choice_text)
                    
                    break
                elif current_element.name == 'p':
                    # Check if this is part of the current question or the next question
                    strong_or_b = current_element.find('strong') or current_element.find('b')
                    if strong_or_b:
                        strong_text = strong_or_b.get_text().strip()
                        # If it starts with a number followed by a dot, it's a new question
                        if question_pattern.match(strong_text):
                            break
                        else:
                            # This might be a continuation of the current question
                            question_parts.append(clean_text(strong_or_b.get_text()))
                elif current_element.name == 'pre':
                    # Capture pre tag content with preserved line breaks
                    if not pre_content:  # Only capture the first pre tag
                        # Get raw text and preserve line breaks, but clean up extra whitespace
                        raw_text = current_element.get_text()
                        # Split by lines, strip each line, and rejoin with newlines
                        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
                        pre_content = '\n'.join(lines)
                elif current_element.name in ['div', 'img']:
                    # Skip these elements but continue looking for choices
                    pass
                
                current_element = current_element.find_next_sibling()
            
            # Combine all question parts
            if len(question_parts) > 1:
                # Special handling for cases like "5. " + "What is used to..."
                combined_parts = []
                for part in question_parts:
                    if re.match(r'^\d+\.\s*$', part):
                        # This is just a question number, add it without extra space
                        combined_parts.append(part.rstrip())
                    else:
                        combined_parts.append(part)
                question_data['question'] = ' '.join(combined_parts)
            elif re.match(r'^\d+\.\s*$', question_text):
                # This is just a question number, look for the next part
                if element.name in ['strong', 'b'] and element.next_sibling:
                    next_elem = element.next_sibling
                    if hasattr(next_elem, 'name') and next_elem.name in ['strong', 'b']:
                        question_data['question'] = question_text.rstrip() + ' ' + clean_text(next_elem.get_text())
            
            # Add pre content if found
            if pre_content:
                question_data['pre'] = pre_content
            
            # Check if this is a special question type first (matching, image-based, etc.)
            question_text_lower = question_text.lower()
            is_special_question = any(keyword in question_text_lower for keyword in ['match', 'question as presented', 'refer to the exhibit', 'place the options in the following order'])
            
            if is_special_question:
                question_data['type'] = 'special'
                question_data['choices'] = []
                question_data['answer'] = "See image for the answer"
                questions.append(question_data)
            elif choices:
                question_data['choices'] = choices
                
                # Set answer format based on number of correct answers
                if len(correct_answers) == 1:
                    question_data['answer'] = correct_answers[0]
                elif len(correct_answers) > 1:
                    question_data['answer'] = correct_answers
                else:
                    # If no correct answer found, check if it might be a special question we missed
                    if any(keyword in question_text_lower for keyword in ['match', 'order', 'drag and drop', 'sequence']):
                        question_data['type'] = 'special'
                        question_data['answer'] = "See image for the answer"
                    else:
                        question_data['answer'] = "Unknown"
                
                questions.append(question_data)
        
        i += 1
    
    return questions

def main():
    if len(sys.argv) != 2:
        print("Usage: python html_to_json_parser.py <html_file_path>")
        sys.exit(1)
    
    html_file_path = Path(sys.argv[1])
    
    if not html_file_path.exists():
        print(f"Error: File {html_file_path} does not exist")
        sys.exit(1)
    
    # Read HTML content
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        print(f"Error reading HTML file: {e}")
        sys.exit(1)
    
    # Extract quiz data
    questions = extract_quiz_data(html_content)
    
    # Determine output file path
    # If input is assets/html/checkpointX.html, output should be assets/json/checkpointX.json
    input_name = html_file_path.stem  # Gets filename without extension
    
    if 'html' in str(html_file_path.parent):
        # Replace 'html' with 'json' in the path
        output_dir = Path(str(html_file_path.parent).replace('html', 'json'))
    else:
        # Same directory as input
        output_dir = html_file_path.parent
    
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file_path = output_dir / f"{input_name}.json"
    
    # Write JSON output
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)
        
        print(f"Successfully extracted {len(questions)} questions")
        print(f"Output saved to: {output_file_path}")
        
    except Exception as e:
        print(f"Error writing JSON file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()