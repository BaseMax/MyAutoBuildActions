import re
import os
import sys
import glob
import shutil
from github import Github
from dotenv import load_dotenv
from binaryornot.check import is_binary

load_dotenv()

PATTERNS = [
  {
    "Key": "Full Name",
    "File": "MyTestApp/app.json",
    "Regex": r'\"name\"\: \"([^\"]+)\",',
  },
  {
    "Key": "App Name",
    "File": "MyTestApp/app.json",
    "Regex": r'\"displayName\"\: \"([^\"]+)\",',
  },
  {
    "Key": "App Name",
    "File": "*",
    "Regex": r'\"displayName\"\: \"([^\"]+)\",',
  },
]
INSTANCES_DIR = ".instances"

# Functions
def has_config(text) -> bool:
    # --- start config ---(.*)--- end config ---
    pattern = r"--- start config ---(.*)--- end config ---"
    # Check if we include the config in the issue body
    return re.search(pattern, text, re.DOTALL)

# Copy whole of sub files and directories to another path except .git, .github, .instances
def copy_project(app_username):
    global INSTANCES_DIR

    # Set the source and destination directories
    src_dir = "." + os.path.sep
    dst_dir = os.path.join(INSTANCES_DIR, app_username) + os.path.sep

    # Iterate over all files and subdirectories in the source directory
    for root, dirs, files in os.walk(src_dir):
        # Exclude directories we don't want to copy
        if ".git" in dirs:
            dirs.remove(".git")
        if ".github" in dirs:
            dirs.remove(".github")
        if INSTANCES_DIR in dirs:
            dirs.remove(INSTANCES_DIR)
        # Remove if the directory name starts with a dot
        for dir in dirs:
            if dir.startswith("."):
                dirs.remove(dir)

        # Create the corresponding directory in the destination directory
        dst_root = root.replace(src_dir, dst_dir)
        os.makedirs(dst_root, exist_ok=True)

        # Copy all files from the source directory to the destination directory
        for file in files:
            src_file = os.path.join(root, file)
            dst_file = os.path.join(dst_root, file)
            shutil.copy(src_file, dst_file)

    return True

def replace_project_dir(target_path, pattern, variable_value):
    # Get all files that match the target path
    files = glob.glob(target_path, recursive=True)
    print("glob:", files)

    # Iterate over all files
    for file in files:
        # Check if the file is a directory
        if os.path.isdir(file) and target_path == file:
            continue
        elif os.path.isdir(file):
            replace_project_dir(file, pattern, variable_value)
            continue
        # Skip binary files
        if is_binary(file):
            continue
        # UTF8 encoding is required for some files
        with open(file, "r+", encoding="utf8") as f:
            content = f.read()
            # Regex to replace all occurences of the pattern and replace group 1 to the variable_value
            new_content = re.sub(pattern["Regex"], f'"\\1": "{variable_value}",', content)
            # Save and close the file
            f.seek(0)
            f.write(new_content)
            f.truncate()
            f.close()

# Looking inside content of all files and subfiles inside the src_dir and replace all occurences of the key of `config` to the new value
def replace_project(app_username, config):
    global INSTANCES_DIR, PATTERNS

    src_dir = os.path.join(INSTANCES_DIR, app_username) + os.path.sep

    # {'Key': 'Full Name', 'File': 'MyTestApp/app.json', 'Regex': '\\"name\\"\\: \\"([^\\"]+)\\",'}
    for pattern in PATTERNS:
        target_path = src_dir + pattern["File"]
        target_path = target_path.replace("/", os.path.sep)
        target_path = target_path.replace("\\", os.path.sep)
        variable_key = pattern["Key"]

        if variable_key in config:
            variable_value = config[variable_key]
        elif "Default" in config:
            variable_value = config["Default"]
        else:
            print("Error: No value for " + variable_key + " in config for " + app_username + " sub-brand")
            return False

        print("target path:", target_path)
        replace_project_dir(target_path, pattern, variable_value)

    return True

def build_project(app_username):
    global INSTANCES_DIR
    
    print("build_project")

    cd = 'cd ' + os.path.join(INSTANCES_DIR, app_username) + ' && '
    cda = 'cd ' + os.path.join(INSTANCES_DIR, app_username, 'android') + ' && '
    print("cd is:", cd)
    commands = [
        cd + 'pwd',
        cd + 'ls -al',
        cd + 'npm install',
        # cd + 'npx react-native bundle --platform android --dev false --entry-file index.js --bundle-output android/app/src/main/assets/index.android.bundle --assets-dest android/app/src/main/res'
        # cd + 'npm run',
        cda + 'gradlew assembleRelease', # windows
        cda + 'ls app/build/outputs/apk/debug/',
    ]
    
    # Run commands
    for command in commands:
        print(command)
        # Execute command
        result = os.system(command)
        # Check for errors
        if result != 0:
            print(f"Command '{command}' failed with error code {result}.")
            return False
    return True

def process_config(config):
    app_username = config["App Username"]

    if copy_project(app_username) == False:
        print("Error: Failed to copy project for " + app_username + " sub-brand")
        return False
    elif replace_project(app_username, config) == False:
        print("Error: Failed to replace project for " + app_username + " sub-brand")
        return False
    elif build_project(app_username) == False:
        print("Error: Failed to build project for " + app_username + " sub-brand")
        return False
    return True

def get_config(text) -> object:
    # Check to make sure we have the config
    if not has_config(text):
        return None

    # --- start config ---(.*)--- end config ---
    pattern = r"--- start config ---(.*)--- end config ---"
    # Get the config from the issue body
    config_text = re.search(pattern, text, re.DOTALL).group(1)
    # Extract keys and values from the config
    # ([a-zA-Z0-9 ]+): (.*)
    config_keys = re.findall(r"([a-zA-Z0-9 ]+): (.*)", config_text)
    keys = {}
    for (key, value) in config_keys:
        value = value.strip().replace('\r', '')
        keys[key] = value
    return keys

# Check arguments and OS ENV
if len(sys.argv) > 1:
    if len(sys.argv) == 3:
        repository_owner = sys.argv[1]
        repository_name = sys.argv[2]
        labels = sys.argv[3].split(",")
    else:
        print("Error: Invalid number of arguments, we expect 3 arguments")
        sys.exit(1)
else:
    repository_owner = os.getenv("REPO_OWNER")
    repository_name = os.getenv("REPO_NAME")
    labels = os.getenv("LABELS")
    if labels:
        labels = labels.split(",")
    else:
        print("Error: No labels provided")
        sys.exit(1)

# Replace with your GitHub access token
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

# Create a GitHub instance using the access token
g = Github(ACCESS_TOKEN)

# Get the repository object
repo = g.get_repo(f"{repository_owner}/{repository_name}")

# Get all the issues in the repository with the "auto-release" label
state = "open"
issues = repo.get_issues(labels=labels, state=state, sort='updated')

# Loop through each issue and get its comments
for issue in issues:
    target_body = None

    # Print the issue title and body
    print(f"Issue: {issue.title}")

    # Get comments of the issue
    comments = issue.get_comments()

    # Check if there are any comments
    if comments.totalCount > 0:
        # Reverse iterate over comments
        for i in range(comments.totalCount - 1, -1, -1):
            comment_body = comments[i].body
            # Check if we have the config in the comment from newest to oldest
            if has_config(comment_body):
                target_body = comment_body
                break
    else:
        print("No comments in this issue")

    # If we not found the config in the comments, check the issue body
    if target_body is None:
        if has_config(issue.body):
            target_body = issue.body

    if target_body is None:
        print("Sorry, no config found in issue body or its comments")
    else:
        print("Config found in body or comments")

        config_keys = get_config(target_body)
        print(config_keys)
        if config_keys == {}:
            print("Error; No keys found in config")
        else:
            # Process a config
            process_config(config_keys)
            break
    
    print("\n\n")
