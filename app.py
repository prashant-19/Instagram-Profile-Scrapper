import os
import shutil
import instaloader
import zipfile
import urllib.parse
from flask import Flask, request, send_file, render_template, after_this_request, jsonify, redirect, url_for
from io import BytesIO
import csv
import time

app = Flask(__name__)
L = instaloader.Instaloader()

status_message = ""  # Global variable to store status messages

def download_profile(username):
    global status_message
    try:
        status_message = "Starting download..."
        L.download_profile(username, profile_pic=True)

        folder_name = username
        os.makedirs(folder_name, exist_ok=True)

        status_message = "Organizing files..."
        for filename in os.listdir('.'):
            if not filename.startswith(username):
                continue
            if filename.endswith('.jpg') or filename.endswith('.mp4'):
                shutil.move(filename, os.path.join(folder_name, filename))

        status_message = "Creating ZIP file..."
        zip_filename = folder_name + '.zip'
        with zipfile.ZipFile(zip_filename, 'w') as zip_file:
            for filename in os.listdir(folder_name):
                extension = os.path.splitext(filename)[1].lower()
                if extension in ['.mp4', '.jpg', '.jpeg', '.png']:
                    zip_file.write(os.path.join(folder_name, filename), arcname=filename)

        shutil.rmtree(folder_name)

        status_message = "Download complete!"
        return zip_filename, None
    except instaloader.exceptions.LoginRequiredException:
        return None, "This profile requires login. Please try a different profile."
    except instaloader.exceptions.ProfileNotExistsException:
        return None, "The profile does not exist. Please check the username."
    except Exception as e:
        return None, f"An error occurred: {str(e)}"

@app.route('/')
def home():
    return render_template('index.html')

def get_username(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc == 'www.instagram.com' and parsed.path != '':
        return parsed.path.split('/')[1]
    return None

@app.route('/download', methods=['POST'])
def download():
    global status_message
    username_or_url = request.form.get('username_or_url')

    username = get_username(username_or_url)

    if username is None:
        username = username_or_url.strip()

    zip_filename, error_message = download_profile(username)

    if error_message:
        status_message = error_message
        return redirect(url_for('home', error_message=error_message))

    # Serve the file in memory to avoid file locking issues
    with open(zip_filename, 'rb') as f:
        file_data = BytesIO(f.read())

    # Cleanup the file after sending
    @after_this_request
    def cleanup(response):
        try:
            time.sleep(1)  # Delay to ensure file is no longer in use
            if os.path.exists(zip_filename):
                os.remove(zip_filename)
                print(f"File {zip_filename} removed successfully.")
            else:
                print(f"File {zip_filename} does not exist.")
        except Exception as e:
            print(f"Error removing file: {e}")
        return response

    status_message = f"Sending file: {zip_filename}"
    file_data.seek(0)
    return send_file(file_data, as_attachment=True, download_name=zip_filename)

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    file = request.files['file']
    
    # Check if a file was uploaded
    if not file:
        return redirect(url_for('home', error_message="No file uploaded!"))

    # Read the CSV file in text mode
    stream = file.stream.read().decode('utf-8').splitlines()  # Decode the stream to a string

    # Initialize CSV reader
    csv_reader = csv.reader(stream)
    usernames = []

    # Read each row and handle both row-wise and column-wise usernames
    for row in csv_reader:
        for username in row:
            if username.strip():  # Ensure no empty usernames are added
                usernames.append(username.strip())

    # Ensure we have usernames after processing the CSV
    if not usernames:
        return redirect(url_for('home', error_message="No valid usernames found in the CSV!"))

    # Create a temporary file for combined ZIP
    combined_zip_fp = BytesIO()
    with zipfile.ZipFile(combined_zip_fp, 'w') as combined_zip:
        for username in usernames:
            zip_filename, error_message = download_profile(username)
            if error_message:
                status_message = error_message
                return redirect(url_for('home', error_message=error_message))
            
            # Add each profile's ZIP to the combined ZIP
            with open(zip_filename, 'rb') as f:
                combined_zip.writestr(os.path.basename(zip_filename), f.read())

    combined_zip_fp.seek(0)

    # Cleanup after sending
    @after_this_request
    def cleanup(response):
        try:
            # Remove individual profile ZIPs
            for username in usernames:
                zip_filename = username + '.zip'
                if os.path.exists(zip_filename):
                    os.remove(zip_filename)
            # No need to remove combined_zip_fp as it's in memory
        except Exception as e:
            print(f"Error during cleanup: {e}")
        return response

    return send_file(combined_zip_fp, as_attachment=True, download_name='combined_profiles.zip')

@app.route('/status')
def status():
    global status_message
    return jsonify({"status": status_message})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
