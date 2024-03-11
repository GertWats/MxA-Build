# osc_manager.py
import os
import json
import struct
import streamlit as st
from config_manager import working_directory

def load_mapping(filename='mapping.json', working_directory=None):
    mapping_file_path = os.path.join(working_directory, filename) if working_directory else filename
    try:
        with open(mapping_file_path, 'r') as f:
            mapping = json.load(f)
        return mapping
    except FileNotFoundError:
        st.error(f"Failed to load mapping file. Expected location: {mapping_file_path}")
        return {}
    
    
def db_to_mapped_value(db_value, mapping):
    db_value_rounded = str(round(db_value))
    if db_value_rounded in mapping:
        return mapping[db_value_rounded]
    else:
        raise ValueError(f"No mapping found for dB value: {db_value}")

        
def create_osc_message(address, value):
    # OSC address pattern, null-terminated and padded to 32-bit boundary
    address = address.encode('utf-8')
    address_padded = address + b'\x00' * (4 - (len(address) % 4))

    # OSC type tag string for a single float argument, null-terminated and padded to 32-bit boundary
    type_tag = b',f' + b'\x00' * (4 - (2 % 4))  # ",f" is 2 bytes, so pad with 2 null bytes

    # OSC argument: pack the float value into 4 bytes
    value_packed = struct.pack(">f", value)

    # Concatenate the parts to form the complete OSC message
    message = address_padded + type_tag + value_packed
    return message


def generate_osc_messages(config, artist_toggles, instrument_toggles, working_directory=None):
    osc_messages = []
    num_toggles = config.get('num_toggles', 1)
    num_instruments = config.get('num_instruments', 0)
    num_fx_units = config.get('num_fx_units', 0)

    # Load the mapping from mapping.json
    mapping = load_mapping('mapping.json', working_directory)
    if mapping:
        pass  # Mapping file loaded successfully
    else:
        mapping_file_path = os.path.join(working_directory, 'mapping.json')
        st.error(f"Failed to load mapping file. Expected location: {mapping_file_path}")

    for i in range(num_toggles):
        artist_name = config.get(f'name{i+1}', '')
        ch_map = config.get(f'ch_map{i+1}', 0)
        fx_unit = config.get(f'effects_unit{i+1}', 0)
        fx_level = config.get(f'effects_ref_level{i+1}', 0.0)
        co_artist_level = config.get(f'co_artists_ref_level{i+1}', 0.0)
        aux_map = config.get(f'aux_map{i+1}', 0)

        if artist_toggles[i]:  # If artist toggle is enabled
            # Set artist ch_map fader to 0dB (0.76)
            osc_messages.append(create_osc_message(f"/sd/Input_Channels/{ch_map}/fader", 0.76))

            # Set artist ch_map mute to 0 (unmuted)
            osc_messages.append(create_osc_message(f"/sd/Input_Channels/{ch_map}/mute", 0))

            for j in range(num_toggles):
                if i != j:  # Skip the current artist
                    other_ch_map = config.get(f'ch_map{j+1}', 0)
                    other_fx_unit = config.get(f'effects_unit{j+1}', 0)
                    other_fx_level = config.get(f'effects_ref_level{j+1}', 0.0)
                    other_co_artist_level = config.get(f'co_artists_ref_level{j+1}', 0.0)
                    other_aux_map = config.get(f'aux_map{j+1}', 0)

                    if artist_toggles[j]:  # If other artist toggle is enabled
                        # Send current artist's channel to other enabled artist's aux at the specified co-artist level
                        mapped_co_artist_level = db_to_mapped_value(co_artist_level, mapping)
                        osc_messages.append(create_osc_message(f"/sd/Input_Channels/{ch_map}/Aux_Send/{other_aux_map}/send_on", 1))
                        osc_messages.append(create_osc_message(f"/sd/Input_Channels/{ch_map}/Aux_Send/{other_aux_map}/send_level", mapped_co_artist_level))
                    else:  # If other artist toggle is disabled
                        # Send current artist's channel to other disabled artist's aux at -inf dB
                        osc_messages.append(create_osc_message(f"/sd/Input_Channels/{ch_map}/Aux_Send/{other_aux_map}/send_on", 0))
                        osc_messages.append(create_osc_message(f"/sd/Input_Channels/{ch_map}/Aux_Send/{other_aux_map}/send_level", 0))

            for k in range(num_fx_units):
                fx_unit_name = config.get(f'fx_unit{k+1}', '')
                fx_ch_map = config.get(f'fx_ch_map{k+1}', 0)
                fx_aux_map = config.get(f'fx_aux_map{k+1}', 0)

                if fx_unit == k+1:  # If FX unit matches the artist's FX unit
                    # Set FX unit channel map fader to 0dB (0.76)
                    osc_messages.append(create_osc_message(f"/sd/Input_Channels/{fx_ch_map}/fader", 0.76))

                    # Set FX unit channel map mute to 0 (unmuted)
                    osc_messages.append(create_osc_message(f"/sd/Input_Channels/{fx_ch_map}/mute", 0))

                    # Send current artist's channel to FX unit at 0dB
                    osc_messages.append(create_osc_message(f"/sd/Input_Channels/{ch_map}/Aux_Send/{fx_aux_map}/send_on", 1))
                    osc_messages.append(create_osc_message(f"/sd/Input_Channels/{ch_map}/Aux_Send/{fx_aux_map}/send_level", 0.76))

                    # Send FX unit to current artist's aux at the specified FX level
                    mapped_fx_level = db_to_mapped_value(fx_level, mapping)
                    osc_messages.append(create_osc_message(f"/sd/Input_Channels/{fx_ch_map}/Aux_Send/{aux_map}/send_on", 1))
                    osc_messages.append(create_osc_message(f"/sd/Input_Channels/{fx_ch_map}/Aux_Send/{aux_map}/send_level", mapped_fx_level))

                    other_enabled_artists = sum(artist_toggles) - artist_toggles[i]
                    if other_enabled_artists == 0:  # If no other artists are enabled
                        for j in range(num_toggles):
                            if i != j:  # Skip the current artist
                                other_aux_map = config.get(f'aux_map{j+1}', 0)
                                # Turn off FX unit send to other artists' auxes
                                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{fx_ch_map}/Aux_Send/{other_aux_map}/send_on", 0))
                                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{fx_ch_map}/Aux_Send/{other_aux_map}/send_level", 0))
                    else:
                        for j in range(num_toggles):
                            if i != j and artist_toggles[j]:  # If other artist is enabled
                                other_aux_map = config.get(f'aux_map{j+1}', 0)
                                other_fx_unit = config.get(f'effects_unit{j+1}', 0)
                                other_fx_level = config.get(f'effects_ref_level{j+1}', 0.0)
                                other_co_artist_level = config.get(f'co_artists_ref_level{j+1}', 0.0)

                                if config.get(f'effects_unit{j+1}', 0) != fx_unit:  # Check for different FX units
                                    # Sum of other artist's co-artist level for current artist + other artist's FX level
                                    summed_level = other_co_artist_level + other_fx_level
                                    mapped_summed_level = db_to_mapped_value(summed_level, mapping)
                                    osc_messages.append(create_osc_message(f"/sd/Input_Channels/{fx_ch_map}/Aux_Send/{other_aux_map}/send_on", 1))
                                    osc_messages.append(create_osc_message(f"/sd/Input_Channels/{fx_ch_map}/Aux_Send/{other_aux_map}/send_level", mapped_summed_level))

                else:  # If FX unit doesn't match the artist's FX unit
                    if not artist_toggles[i]:  # If artist toggle is disabled
                        # Send FX unit to current artist's aux at -inf dB
                        osc_messages.append(create_osc_message(f"/sd/Input_Channels/{fx_ch_map}/Aux_Send/{aux_map}/send_on", 0))
                        osc_messages.append(create_osc_message(f"/sd/Input_Channels/{fx_ch_map}/Aux_Send/{aux_map}/send_level", 0))

        else:  # If artist toggle is disabled
            # Set artist ch_map fader to -inf dB (0)
            osc_messages.append(create_osc_message(f"/sd/Input_Channels/{ch_map}/fader", 0))

            # Set artist ch_map mute to 0 (unmuted)
            osc_messages.append(create_osc_message(f"/sd/Input_Channels/{ch_map}/mute", 0))

            for j in range(num_toggles):
                if i != j:  # Skip the current artist
                    other_ch_map = config.get(f'ch_map{j+1}', 0)
                    other_aux_map = config.get(f'aux_map{j+1}', 0)

                    # Send current artist's channel to other artists' auxes at -inf dB
                    osc_messages.append(create_osc_message(f"/sd/Input_Channels/{ch_map}/Aux_Send/{other_aux_map}/send_on", 0))
                    osc_messages.append(create_osc_message(f"/sd/Input_Channels/{ch_map}/Aux_Send/{other_aux_map}/send_level", 0))

            for k in range(num_fx_units):
                fx_ch_map = config.get(f'fx_ch_map{k+1}', 0)
                fx_aux_map = config.get(f'fx_aux_map{k+1}', 0)

                # Send current artist's channel to FX units at -inf dB
                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{ch_map}/Aux_Send/{fx_aux_map}/send_on", 0))
                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{ch_map}/Aux_Send/{fx_aux_map}/send_level", 0))

                # Send FX units to current artist's aux at -inf dB
                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{fx_ch_map}/Aux_Send/{aux_map}/send_on", 0))
                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{fx_ch_map}/Aux_Send/{aux_map}/send_level", 0))
        
        # Featured Instruments OSC Logic
        for i in range(num_instruments):
            inst_ch_map = config.get(f'inst_ch_map{i+1}', 0)
            inst_fx_unit = config.get(f'inst_fx_unit{i+1}', 0)
            inst_fx_lvl = config.get(f'inst_fx_lvl{i+1}', 0)
            fx_aux_map = config.get(f'fx_aux_map{inst_fx_unit}', 0)

            if instrument_toggles[i]:  # If the featured instrument toggle is on
                # Set instrument channel fader to 0dB (0.76)
                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{inst_ch_map}/fader", 0.76))

                # Set instrument channel mute to 0 (unmuted)
                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{inst_ch_map}/mute", 0))
                
                # Set FX unit channel map fader to 0dB (0.76)
                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{fx_ch_map}/fader", 0.76))

                # Set FX unit channel map mute to 0 (unmuted)
                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{fx_ch_map}/mute", 0))

                # Send instrument channel to FX unit at the specified level
                mapped_inst_fx_lvl = db_to_mapped_value(inst_fx_lvl, mapping)
                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{inst_ch_map}/Aux_Send/{fx_aux_map}/send_on", 1))
                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{inst_ch_map}/Aux_Send/{fx_aux_map}/send_level", mapped_inst_fx_lvl))

            else:  # If the featured instrument toggle is off
                # Set instrument channel fader to -inf dB (0)
                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{inst_ch_map}/fader", 0))

                # Set instrument channel mute to 1 (muted)
                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{inst_ch_map}/mute", 1))

                # Turn off the send from the instrument channel to FX unit
                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{inst_ch_map}/Aux_Send/{fx_aux_map}/send_on", 0))
                osc_messages.append(create_osc_message(f"/sd/Input_Channels/{inst_ch_map}/Aux_Send/{fx_aux_map}/send_level", 0))

    return osc_messages

def send_osc_batch(ip, port, messages):
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        for message in messages:
            sock.sendto(message, (ip, int(port)))
    finally:
        sock.close() 