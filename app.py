import os
import shutil
import instaloader
import zipfile
import time
import urllib.parse
from flask import Flask, request, jsonify, send_file, render_template

app = Flask(__name__)
L= instaloader.Instaloader()

def download_profile(username):
    try:
        L.download_profile(username, profile_pic=True)

        folder_name = username
        os.makedirs(folder_name, exist_ok=True)

        for filename in os.listdir('.'):
            if not filename.startswith(username):
                continue
            if filename.endswith('.jpg') or filename.endswith('.mp4'):
                shutil.move(filename, os.path.join(folder_name, filename))

        zip_filename = folder_name + '.zip'
        with zipfile.ZipFile(zip_filename, 'w') as zip_file:
            for filename in os.listdir(folder_name):
                extension = os.path.splitext(filename)[1].lower()
                if extension in ['.mp4', '.jpg', '.jpeg', 'png']:
                    zip_file.write(os.path.join(folder_name, filename), arcname=filename)

        shutil.rmtree(folder_name)

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
    username_or_url = request.form.get('username_or_url')

    username = get_username(username_or_url)

    if username is None:
        username = username_or_url.strip()

    zip_filename, error_message = download_profile(username)

    if error_message:
        return render_template('index.html', error_message=error_message)
    
    return send_file(zip_filename, as_attachment=True)   

if __name__ == "__main__":
    
    app.run(host='0.0.0.0', port=5000)
    app.run(debug=True)




    