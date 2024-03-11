# app.py
import streamlit as st
import socket
import json
import subprocess
import signal
import sys
import struct
from config_manager import save_config, download_config, load_config_file, load_config, update_config, working_directory
from osc_manager import generate_osc_messages, send_osc_batch
import logging
import os

st.set_page_config(page_title="MxA | MixAssistant")

def get_int_config(config, key, default=0):
    value_str = config.get(key, str(default))
    return int(value_str) if value_str.isdigit() else default

def load_mapping(filename='mapping.json'):
    try:
        with open(filename, 'r') as f:
            mapping = json.load(f)
        return mapping
    except FileNotFoundError:
        return {}

def get_diagnostics():
    diagnostics = {
        "Current PATH": os.environ.get('PATH'),
        "Current Working Directory": working_directory,
        "User": os.environ.get('USER'),
        "Python Executable": sys.executable,
        "Python Version": sys.version,
    }
    return diagnostics

def generate_qr_code(url):
    import qrcode
    from io import BytesIO

    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img_byte_array = BytesIO()
    img.save(img_byte_array, format='PNG')
    return img_byte_array.getvalue()

def find_process_listening_on_port(port):
    command = f"lsof -i :{port} | grep LISTEN"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    for process_line in stdout.splitlines():
        if f":{port}" in process_line.decode('utf-8'):
            pid = int(process_line.split(None, 2)[1])
            return pid
    return None

def terminate_process_on_port(port):
    pid = find_process_listening_on_port(port)
    if pid is None:
        st.warning(f"No process found listening on port {port}.")
    else:
        os.kill(pid, signal.SIGTERM)
        st.success(f"Terminated process {pid} on port {port}.")

def main():
    st.title("Mix Assistant | Live v5")

    # Load the configuration only if it's not already in the session state
    if "config" not in st.session_state:
        config = load_config()
        st.session_state.config = config
    else:
        config = st.session_state.config

    # Initialize the current page in session state if it doesn't exist
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'setup'  # Default to setup page

    # Create buttons for switching between pages
    col1, col2, col3 = st.columns([1, 1, 4], gap="small")
    with col1:
        setup_page_button = st.button("Setup Page")
    with col2:
        show_page_button = st.button("Show Page")

    # Update the current page in session state based on button clicks
    if setup_page_button:
        st.session_state.current_page = 'setup'
    elif show_page_button:
        st.session_state.current_page = 'show'

    # Display the appropriate page based on the current_page session state
    if st.session_state.current_page == 'setup':
        setup_page(config)
    elif st.session_state.current_page == 'show':
        show_page(config)

def setup_page(config):
    st.title("Console Setup")

    # Input fields for console IP, send port, and receive port
    console_ip = st.text_input("Console IP", value=config.get('console_ip', ''), key="console_ip")
    send_port = st.text_input("Send Port", value=config.get('send_port', ''), key="send_port")
    receive_port = st.text_input("Receive Port", value=config.get('receive_port', ''), key="receive_port")

    with st.expander("Artists Setup"):
        st.title("Artists Setup")

        # Input field for number of Artists
        num_toggles = st.number_input("Number of Artists", 1, 32, value=config.get('num_toggles', 1))

        # Headers for the Artist setup table
        col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 3, 1, 1, 2, 1, 2])
        col1.text('No.')
        col2.text('Artist Name')
        col3.text('ChMap')
        col4.text('AuxMap')
        col5.text('CoArtist Lvl')
        col6.text('FXUnit')
        col7.text('FX Lvl')

        # Dynamic creation of input fields for Artists
        names = []
        ch_maps = []
        aux_maps = []
        co_artists_ref_levels = []
        effects_units = []
        effects_ref_levels = []
        for i in range(num_toggles):
            col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 3, 1, 1, 2, 1, 2])
            with col1:
                st.write("")
                st.write("")
                st.text(i+1)  # display the row number
            with col2:
                name = st.text_input("ArtistName", key=f"name{i+1}", value=config.get(f'name{i+1}', ''), label_visibility='hidden')
                names.append(name)
            with col3:
                ch_map = st.number_input("ChMap", key=f"ch_map{i+1}", value=config.get(f'ch_map{i+1}', 0), label_visibility='hidden')
                ch_maps.append(ch_map)
            with col4:
                aux_map = st.number_input("AuxMap", key=f"aux_map{i+1}", value=config.get(f'aux_map{i+1}', 0), label_visibility='hidden')
                aux_maps.append(aux_map)
            with col5:
                co_artists_ref_level = st.number_input("ArtReflvl", key=f"co_artists_ref_level{i+1}", value=config.get(f'co_artists_ref_level_input{i+1}', 0), label_visibility='hidden')
                co_artists_ref_levels.append(co_artists_ref_level)
            with col6:
                effects_unit = st.number_input("FXUnit", key=f"effects_unit{i+1}", value=config.get(f'effects_unit{i+1}', 0), label_visibility='hidden')
                effects_units.append(effects_unit)
            with col7:
                effects_ref_level = st.number_input("FXRefLvl", key=f"effects_ref_level{i+1}", value=config.get(f'effects_ref_level_input{i+1}', 0), label_visibility='hidden')
                effects_ref_levels.append(effects_ref_level)

    # Section for Featured Instruments
    with st.expander("Featured Instruments"):
        st.title("Featured Instruments Setup")

        # Input field for number of Featured Instruments
        num_instruments = st.number_input("Number of Featured Instruments", 0, 32, value=config.get('num_instruments', 1))

        # Headers for the Featured Instruments setup table
        col1, col2, col3, col4, col5 = st.columns([1, 2, 1, 1, 1])
        col1.text('No.')
        col2.text('Inst Name')
        col3.text('Inst ChMap')
        col4.text('Inst FXUnit')
        col5.text('Inst FXLvl')

        # Dynamic creation of input fields for Featured Instruments
        inst_names = []
        inst_ch_maps = []
        inst_fx_units = []
        inst_fx_lvls = []
        for i in range(num_instruments):
            col1, col2, col3, col4, col5 = st.columns([1, 2, 1, 1, 1])
            with col1:
                st.write("")
                st.write("")
                st.text(i+1)  # display the row number
            with col2:
                name = st.text_input("InstName", key=f"inst_name{i+1}", value=config.get(f'inst_name{i+1}', ''), label_visibility='hidden')
                inst_names.append(name)
            with col3:
                ch_map = st.number_input("InstChMap", key=f"inst_ch_map{i+1}", value=config.get(f'inst_ch_map{i+1}', 0), label_visibility='hidden')
                inst_ch_maps.append(ch_map)
            with col4:
                fx_unit = st.number_input("InstFXUnit", key=f"inst_fx_unit{i+1}", value=config.get(f'inst_fx_unit{i+1}', 0), label_visibility='hidden')
                inst_fx_units.append(fx_unit)
            with col5:
                fx_lvl = st.number_input("InstFXLvl", key=f"inst_fx_lvl{i+1}", value=config.get(f'inst_fx_lvl{i+1}', 0), label_visibility='hidden')
                inst_fx_lvls.append(fx_lvl)

    # Section for FX Setup
    with st.expander("FX Setup"):
        st.title("FX Setup")

        # Input field for number of FX units
        num_fx_units = st.number_input("Number of FX Units", 1, 32, value=config.get('num_fx_units', 1))

        # Headers for the FX Setup table
        col1, col2, col3, col4 = st.columns([1, 3, 1, 1])
        col1.text('No.')
        col2.text('FX Unit')
        col3.text('FXChMap')
        col4.text('FXAuxMap')

        # Dynamic creation of input fields for Effects
        fx_units = []
        fx_ch_maps = []
        fx_aux_maps = []
        for i in range(num_fx_units):
            col1, col2, col3, col4 = st.columns([1, 3, 1, 1])
            with col1:
                st.write("")
                st.write("")
                st.text(i+1)  # display the row number
            with col2:
                fx_unit = st.text_input("FXUnit", key=f"fx_unit{i+1}", value=config.get(f'fx_unit{i+1}', ''), label_visibility='hidden')
                fx_units.append(fx_unit)
            with col3:
                fx_ch_map = st.number_input("FXChMap", key=f"fx_ch_map{i+1}", value=config.get(f'fx_ch_map{i+1}', 0), label_visibility='hidden')
                fx_ch_maps.append(fx_ch_map)
            with col4:
                fx_aux_map = st.number_input("FXAuxMap", key=f"fx_aux_map{i+1}", value=config.get(f'fx_aux_map{i+1}', 0), label_visibility='hidden')
                fx_aux_maps.append(fx_aux_map)

    st.title("Session File Management")

    # Input field for session name
    session_name = st.text_input("Session Name", value=config.get('session_name', ''), key="session_name")
    
    # Button for saving the current state
    if st.button("Save Session"):
        config['console_ip'] = console_ip
        config['send_port'] = send_port
        config['receive_port'] = receive_port

        # Saving Artists Parameters
        config['num_toggles'] = num_toggles
        for i in range(num_toggles):
            config[f'name{i+1}'] = names[i]
            config[f'ch_map{i+1}'] = ch_maps[i]
            config[f'aux_map{i+1}'] = aux_maps[i]
            config[f'co_artists_ref_level{i+1}'] = co_artists_ref_levels[i]
            config[f'effects_unit{i+1}'] = effects_units[i]
            config[f'effects_ref_level{i+1}'] = effects_ref_levels[i]

            # Store original input values
            config[f'co_artists_ref_level_input{i+1}'] = co_artists_ref_levels[i]
            config[f'effects_ref_level_input{i+1}'] = effects_ref_levels[i]

        # Saving Featured Instruments Parameters
        config['num_instruments'] = num_instruments
        for i in range(num_instruments):
            config[f'inst_name{i+1}'] = inst_names[i]
            config[f'inst_ch_map{i+1}'] = inst_ch_maps[i]
            config[f'inst_fx_unit{i+1}'] = inst_fx_units[i]
            config[f'inst_fx_lvl{i+1}'] = inst_fx_lvls[i]

        # Saving Effect Units Parameters
        config['num_fx_units'] = num_fx_units
        for i in range(num_fx_units):
            config[f'fx_unit{i+1}'] = fx_units[i]
            config[f'fx_ch_map{i+1}'] = fx_ch_maps[i]
            config[f'fx_aux_map{i+1}'] = fx_aux_maps[i]

        config['session_name'] = session_name

        update_config(config)

    # Download session file
    filename = download_config(config)
    with open(filename, 'rb') as f:
        btn = st.download_button('Download Session File', f, file_name=os.path.basename(filename))

    # Delete the file after download
    if btn:
        os.remove(filename)

    # Load session file
    uploaded_file = st.file_uploader('Load Session File', type=['json'])

    # Initialize load session counter if it doesn't exist
    if 'load_session_press_count' not in st.session_state:
        st.session_state.load_session_press_count = 0

    # Only show the Load button if it hasn't been pressed twice yet
    if st.session_state.load_session_press_count < 1:
        load_button = st.button('Load Session')
        if load_button:
            if uploaded_file is not None:
                # Increment the load session press count
                st.session_state.load_session_press_count += 1
                
                if st.session_state.load_session_press_count == 1:
                    # First press: show the instruction to press again
                    st.warning("Select 'Load Session' again to confirm.")
                elif st.session_state.load_session_press_count == 2:
                    # Second press: proceed with loading
                    config = load_config_file(uploaded_file)
                    update_config(config)
                    # Reset the counter for future loads
                    st.session_state.load_session_press_count = 0
    else:
        # Once the file is successfully loaded, show a success message
        st.success("Session file successfully loaded.")

    # Terminate app button for selected ports
    if st.button("Terminate App"):
        terminate_process_on_port(8501)
        terminate_process_on_port(8502)
        terminate_process_on_port(8503)

    # QR Code for Streamlit app URL
    st.title("Mobile Barcode")
    hostname = socket.gethostname()
    port = "8501"  # default port for Streamlit
    url = f"http://{hostname}:{port}"
    qr_code = generate_qr_code(url)
    st.image(qr_code, caption="Scan to open the MxA App", width=200)

    # Add diagnostics at the bottom
    st.title("Diagnostics and Logs")
    diagnostics = get_diagnostics()
    for key, value in diagnostics.items():
        st.text(f"{key}: {value}")

    # Printing the last 100 lines of a log file
    log_file_path = os.path.join(working_directory, 'logfile.log')
    # Configure basic logging
    logging.basicConfig(filename=log_file_path, level=logging.INFO)

    try:
        with open(log_file_path, 'r') as log_file:
            log_lines = log_file.readlines()
            last_100_lines = log_lines[-100:]
            st.text("Last 100 lines of the log file:")
            st.text("".join(last_100_lines))
    except FileNotFoundError:
        st.warning(f"Log file not found: {log_file_path}")

def show_page(config):
    # Initialize debug_info as an empty list
    debug_info = []

    # Load the mapping and configuration
    mapping = load_mapping('mapping.json')
    console_ip = config.get('console_ip', '')
    send_port = get_int_config(config, 'send_port', 0)  # Provide a default value of 0 if send_port is missing or empty
    osc_messages = []

    num_toggles = config.get('num_toggles', 1)
    num_instruments = config.get('num_instruments', 0)

    # Initialize names array for artists and instruments
    artist_names = [config.get(f'name{i+1}', f'Artist {i+1}') for i in range(num_toggles)]
    instrument_names = [config.get(f'inst_name{i+1}', f'Instrument {i+1}') for i in range(num_instruments)]

    st.title("Artists Live")

    # Create a matrix of toggle switches for Artists in a 4-column layout
    for i in range(0, num_toggles, 4):
        cols = st.columns(4)  # Create 4 columns
        for j in range(4):
            if i + j < num_toggles:  # Check if there's an artist to display
                with cols[j]:
                    toggle_state = config.get(f'toggle_page2_{i+j+1}', False)
                    artist_toggle = st.toggle(artist_names[i+j], key=f'artist_toggle_{i+j}', value=toggle_state)
                    config[f'toggle_page2_{i+j+1}'] = artist_toggle

    st.title("Featured Instruments Live")

    # Create a matrix of toggle switches for featured instruments in a 4-column layout
    for i in range(0, num_instruments, 4):
        cols = st.columns(4)  # Create 4 columns
        for j in range(4):
            if i + j < num_instruments:  # Check if there's an instrument to display
                with cols[j]:
                    toggle_state = config.get(f'inst_toggle_{i+j+1}', False)
                    instrument_toggle = st.toggle(instrument_names[i+j], key=f'instrument_toggle_{i+j}', value=toggle_state)
                    config[f'inst_toggle_{i+j+1}'] = instrument_toggle
                    
    # Reconstruct artist_toggles and instrument_toggles lists from config
    artist_toggles = [config.get(f'toggle_page2_{i+1}', False) for i in range(num_toggles)]
    instrument_toggles = [config.get(f'inst_toggle_{i+1}', False) for i in range(num_instruments)]
    
    # Call generate_osc_messages with the reconstructed lists
    osc_messages = generate_osc_messages(config, artist_toggles, instrument_toggles, working_directory)

    st.write("#")

    if st.button("Send to Console"):
        # Generate OSC messages based on the toggle states and configurations
        osc_messages = generate_osc_messages(config, artist_toggles, instrument_toggles, working_directory)
        
        # Add an expander to list each of the commands sent in an easy-to-read format
        with st.expander("See OSC Commands Sent", expanded=False):
            for msg in osc_messages:
                # Decode the address from the OSC message
                address_end_index = msg.find(b'\x00', 1)
                address = msg[:address_end_index].decode('utf-8').strip('\x00')

                # Find the type tag start
                type_tag_index = address_end_index + (4 - (address_end_index % 4))  # Skip to end of padding
                type_tag_start = msg.find(b',', type_tag_index) + 1  # Find start of type tags
                type_tag_end = msg.find(b'\x00', type_tag_start)
                type_tag = msg[type_tag_start+1:type_tag_end].decode('utf-8', errors='ignore')
                type_tags = msg[type_tag_start:type_tag_end].decode('utf-8')

                # Decode the value(s) based on the type tag
                values = []
                value_start_index = type_tag_end + (4 - (type_tag_end % 4))  # Adjust for padding
                values = []  # To handle multiple values if needed
                for tag in type_tags:
                    if tag == 'i':
                        # Ensure buffer is large enough for an integer
                        if value_start_index + 4 <= len(msg):  # 4 bytes for integer
                            value, = struct.unpack_from('>i', msg, value_start_index)
                            value_start_index += 4
                            values.append(str(value))
                        else:
                            print("Error: Buffer too small for unpacking integer")
                            # Handle the error (skip or log)

                    elif tag == 'f':
                        # Ensure buffer is large enough for a float
                        if value_start_index + 4 <= len(msg):  # 4 bytes for float
                            value, = struct.unpack_from('>f', msg, value_start_index)
                            value_start_index += 4
                            values.append(str(value))
                        else:
                            print("Error: Buffer too small for unpacking float")
                            # Handle the error (skip or log)

                # Combine address, type tags, and values into a readable message
                readable_msg = f"{console_ip} {send_port} {address} {' '.join(type_tags + ' ' + v for v in values)}"
                st.text(readable_msg)

        st.write("#")

        # Display debugging information at the end (if any)
        for info in debug_info:
            st.text(info)

        # Send all constructed OSC messages in a batch
        if osc_messages:
            send_osc_batch(console_ip, send_port, osc_messages)
            st.success("OSC messages sent successfully.")
        else:
            st.warning("No OSC messages to send.")

        # Save the state of Artists Live toggles
        for i in range(num_toggles):
            config[f'toggle_page2_{i+1}'] = artist_toggles[i]

        # Save the state of Featured Instruments Live toggles
        for i in range(num_instruments):
            config[f'inst_toggle_{i+1}'] = instrument_toggles[i]

        update_config(config)

if __name__ == "__main__":
    main()