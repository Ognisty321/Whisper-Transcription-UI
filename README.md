# Whisper Transcription UI

## Overview

**Whisper Transcription UI** is a user-friendly graphical user interface (GUI) designed for the [whisper-standalone-win](https://github.com/Purfview/whisper-standalone-win) tool. With this tool, you can easily transcribe or translate audio and video files using various Whisper models. The application allows customization of settings and saves your preferences for future use.

![screenshot](https://i.imgur.com/sX0NlZi.png)

## Features

- **Easy file selection:** Browse, select, or paste multiple audio and video files.
- **Customizable settings:** Adjust transcription options such as language, model, task (transcribe/translate), output format, and more.
- **Advanced options:** Enable/disable options such as FF MDX Kim2, VAD filter, word timestamps, and set advanced parameters like temperature, beam size, and more.
- **Progress tracking:** Monitor the transcription progress of your files.
- **Save settings:** Save your transcription and advanced settings for future sessions.
- **Logging:** Enable/disable logging to keep track of the transcription process and errors.
- **URL Support:** Directly input URLs to transcribe audio from online sources.
- **Drag and Drop:** Supports drag-and-drop file selection.

## Installation

### Prerequisites
- **[Whisper Standalone](https://github.com/Purfview/whisper-standalone-win/releases):** Download and install the latest release of whisper-standalone-win.
- Python 3.x

### Steps

1. Clone the repository:
    ```sh
    git clone https://github.com/OgnistyPoland/whisper-transcription-ui.git
    cd whisper-transcription-ui
    ```

2. Install required packages:
    ```sh
    pip install tkinterdnd2 ttkbootstrap yt-dlp
    ```

3. Run the application:
    ```sh
    python main.py
    ```

## Usage

1. **Select Files:** Click the `Browse` button to select multiple audio or video files. You can also drag and drop files or paste a file path/URL into the provided field.
2. **Set Output Directory:** Choose the directory where you want the output files to be saved.
3. **Choose Options:** Adjust the transcription options such as:
   - **Language:** Select the language spoken in the audio.
   - **Model:** Choose the Whisper model to use.
   - **Task:** Select whether to transcribe or translate.
   - **Output Format:** Choose the desired output format.
4. **Advanced Options:** Configure advanced features and parameters.
5. **Transcribe:** Click the `Transcribe` button to start the transcription process.
6. **Save Settings:** Click the `Save Settings` button to save your current settings for future sessions.

## Configuration File

The application uses a configuration file (`config.ini`) to save your settings. This file will be created automatically in the application directory the first time you run the program and click the `Save Settings` button.

## Acknowledgments

This project was created as a user interface for the [whisper-standalone-win](https://github.com/Purfview/whisper-standalone-win) tool. Special thanks to the developers of whisper-standalone-win for the amazing transcription tool.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Contact

For any questions or suggestions, feel free to reach out to [OgnistyPoland](https://github.com/OgnistyPoland).
