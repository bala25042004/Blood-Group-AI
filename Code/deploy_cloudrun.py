#!/usr/bin/env python3
"""
Google Cloud Run Deployment Script
=================================
Deploys the Flask app to Google Cloud Run.

Usage:
    python deploy_cloudrun.py
"""

import os
import subprocess
import sys

def print_step(message):
    print(f"\n=== {message} ===")

def run_command(cmd, shell=True):
    """Run a command and return output"""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    print(result.stdout)
    return True

def main():
    print("""
=====================================================
   Blood Eye Project - Cloud Run Deployment
=====================================================
    """)

    # Check if gcloud is installed
    print_step("Checking Google Cloud SDK")
    if not run_command("gcloud --version"):
        print("ERROR: Google Cloud SDK not installed!")
        print("Install from: https://cloud.google.com/sdk/docs/install")
        sys.exit(1)

    # Check authentication
    print_step("Checking authentication")
    if not run_command('gcloud auth list --filter=status:ACTIVE --format="value(account)"'):
        print("ERROR: Not logged in to Google Cloud!")
        print("Run: gcloud auth login")
        sys.exit(1)

    # Set project
    project_id = input("\nEnter your Google Cloud Project ID: ").strip()
    if not project_id:
        print("ERROR: Project ID is required!")
        sys.exit(1)

    print_step(f"Setting project to: {project_id}")
    run_command(f'gcloud config set project {project_id}')

    # Enable required APIs
    print_step("Enabling required APIs")
    run_command("gcloud services enable run.googleapis.com containerregistry.googleapis.com")

    # Build and deploy
    print_step("Building and deploying to Cloud Run")
    
    image_name = f"gcr.io/{project_id}/blood-eye-app"
    
    # Build
    build_cmd = f'gcloud builds submit --tag {image_name} .'
    print(f"Building container image...")
    if not run_command(build_cmd):
        print("ERROR: Build failed!")
        sys.exit(1)

    # Deploy
    deploy_cmd = f'gcloud run deploy blood-eye-app --image {image_name} --platform managed --region us-central1 --allow-unauthenticated'
    print(f"Deploying to Cloud Run...")
    if not run_command(deploy_cmd):
        print("ERROR: Deployment failed!")
        sys.exit(1)

    print("""
=====================================================
   Deployment Complete!
=====================================================

Your app is now deployed on Google Cloud Run.

To find the URL, run:
    gcloud run services describe blood-eye-app --platform managed --region us-central1 --format="value(status.url)"
""")

if __name__ == '__main__':
    main()
