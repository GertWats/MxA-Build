# config_manager.py
import os
import json
import struct
import streamlit as st

working_directory = os.path.join(os.path.expanduser('~'), 'Documents', 'MxA')
os.makedirs(working_directory, exist_ok=True)

CONFIG_FILE = os.path.join(working_directory, 'config.json')

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        st.error(f"Failed to save configuration: {e}")

def update_config(config):
    st.session_state.config = config
    save_config(config)

def download_config(config):
    download_file_path = os.path.join(working_directory, 'downloaded_config.json')
    with open(download_file_path, 'w') as f:
        json.dump(config, f, indent=4)
    return download_file_path

def load_config_file(file):
    try:
        config = json.load(file)
        return config
    except json.JSONDecodeError:
        return {}