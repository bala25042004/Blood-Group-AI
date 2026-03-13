# Git Collaboration Setup Guide for Blood Eye Project

This guide will help you set up Git version control to collaborate with your friend on the Blood Eye Project.

---

## PREREQUISITES

Before starting, make sure you have Git installed on both computers:

- Download from: https://git-scm.com/download/win

---

## PART 1: YOUR LAPTOP SETUP (First Time)

### Step 1: Open Terminal/Command Prompt

Open Command Prompt (cmd) or PowerShell in your project folder:

```
cd C:\Users\USER\Music\Blood Eye Project
```

### Step 2: Initialize Git Repository

This command creates a new Git repository in your project folder:

```
git init
```

### Step 3: Configure Your Identity

Set your name and email (this identifies your commits):

```
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
```

### Step 4: Create .gitignore File

Create a file to exclude unnecessary files from Git (already exists in your project):

```
type nul > .gitignore
```

Or create it with content to ignore Python/virtual environment files:

```
echo __pycache__/ > .gitignore
echo .venv/ >> .gitignore
echo .venv312/ >> .gitignore
echo *.pyc >> .gitignore
echo uploads/ >> .gitignore
echo .env >> .gitignore
```

### Step 5: Add All Files to Staging

This prepares all your files for their first commit:

```
git add .
```

### Step 6: Create Your First Commit

This saves a snapshot of your current project:

```
git commit -m "Initial commit - first version of Blood Eye Project"
```

### Step 7: Connect to GitHub Remote

This links your local repository to GitHub:

```
git remote add origin https://github.com/bala25042004/Blood-Group-AI.git
```

### Step 8: Verify Remote Connection

This shows your connected remote repository:

```
git remote -v
```

### Step 9: Push to GitHub

This uploads your code to GitHub for the first time:

```
git push -u origin main
```

Note: If it asks for username/password, use your GitHub credentials or personal access token.

---

## PART 2: YOUR FRIEND'S LAPTOP SETUP (First Time)

### Step 1: Install Git

Your friend should download and install Git from https://git-scm.com/download/win

### Step 2: Open Terminal

Open Command Prompt and navigate to where your friend wants the project:

```
cd C:\Users\Friend\Documents
```

### Step 3: Clone the Repository

This downloads the entire project from GitHub to your friend's laptop:

```
git clone https://github.com/bala25042004/Blood-Group-AI.git
```

After this, a folder called "Blood-Group-AI" will be created with all your code.

### Step 4: Navigate Into the Project Folder

```
cd Blood-Group-AI
```

### Step 5: Configure Your Friend's Identity

```
git config --global user.name "Friend's Name"
git config --global user.email "friend@email.com"
```

### Step 6: Install Project Dependencies

Your friend needs to install Python packages:

```
pip install -r requirements.txt
```

---

## PART 3: DAILY WORKFLOW

### WHEN YOU MAKE CHANGES (You - on your laptop)

#### Step 1: Check Status

See which files you've changed:

```
git status
```

#### Step 2: Add Changed Files

Stage the files you modified:

```
git add .
```

Or to add specific files:

```
git add filename.py
```

#### Step 3: Commit Changes

Save your changes with a message:

```
git commit -m "Description of what you changed"
```

#### Step 4: Push to GitHub

Upload your changes to GitHub:

```
git push origin main
```

### WHEN YOUR FRIEND MAKES CHANGES (Friend - on their laptop)

#### Step 1: Pull Latest Changes

Download the latest changes from GitHub:

```
git pull origin main
```

---

## PART 4: HANDLING CONFLICTS

If both of you edit the same file, Git will warn you about conflicts. Here's how to resolve:

1. When you pull and see "CONFLICT", open the file
2. Look for markers like `<<<<<<< HEAD`, `=======`, `>>>>>>>`
3. Keep the code you want, remove the conflict markers
4. Save the file, then:

```
git add filename.py
git commit -m "Resolved conflict in filename.py"
git push origin main
```

---

## HELPFUL GIT COMMANDS

| Command                   | What it does                |
| ------------------------- | --------------------------- |
| `git status`              | Show changed files          |
| `git diff`                | Show exact changes made     |
| `git log`                 | Show commit history         |
| `git pull`                | Download latest from GitHub |
| `git push`                | Upload to GitHub            |
| `git add .`               | Stage all changes           |
| `git commit -m "message"` | Save changes                |

---

## IMPORTANT TIPS

1. **Always pull before starting work**: Run `git pull origin main` before making changes
2. **Always push after finishing work**: Run `git push origin main` when done
3. **Communicate with your friend**: Tell each other when you're working on the project
4. **Write clear commit messages**: Describe what you changed briefly
5. **Don't push large files**: Keep images/models out of Git or use Git LFS

---

## RUNNING YOUR PROJECT

After pulling changes, always install/update dependencies:

```
pip install -r requirements.txt
```

Then run your Flask app:

```
python app.py
```

---

END OF GUIDE
