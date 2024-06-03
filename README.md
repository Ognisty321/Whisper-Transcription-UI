# Whisper Transcription UI

<img src="https://i.imgur.com/udv3MhH.png" alt="screenshot" width="50%" height="auto"/>

## Overview

**Whisper Transcription UI** is a user-friendly graphical user interface (GUI) for the [whisper-standalone-win](https://github.com/Purfview/whisper-standalone-win) tool. 

This intuitive application simplifies audio and video transcription and translation using various Whisper models. Customize settings to your liking and save them for future use.

## ✨ Features

- **Effortless File Handling:** Browse, select, paste, or drag and drop multiple audio and video files.
- **Direct URL Input:** Transcribe audio from online sources by providing the URL.
- **Flexible Transcription Options:** 
    - Select the target language.
    - Choose the Whisper model that best suits your needs.
    - Transcribe or translate with ease. 
    - Define your preferred output format.
- **Advanced Customization:** Fine-tune transcription parameters like FF MDX Kim2, VAD filter, word timestamps, temperature, and beam size.
- **Progress Monitoring:** Keep track of the transcription process.
- **Persistent Settings:** Save your preferred transcription and advanced settings.
- **Detailed Logging:** Enable logging to monitor the transcription process and troubleshoot any issues.

## 🚀 Getting Started

### Prerequisites

- **[Whisper Standalone](https://github.com/Purfview/whisper-standalone-win/releases):** Download and install the latest release.
- **Python 3.x**

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Ognisty321/whisper-transcription-ui.git
   cd whisper-transcription-ui
   ```

2. Install required packages:
   ```bash
   pip install tkinterdnd2 ttkbootstrap yt-dlp
   ```

3. Launch the application:
   ```bash
   python main.py
   ```

## 🎬 Usage

1. **Select Files:** Click `Browse` to choose files, drag and drop them into the interface, or paste file paths/URLs.
2. **Set Output Directory:** Specify where transcribed files should be saved.
3. **Choose Options:** Configure transcription language, model, task (transcribe/translate), output format, and other options.
4. **Advanced Options:** Fine-tune your transcription using advanced features and parameters.
5. **Transcribe:** Initiate the transcription process by clicking the `Transcribe` button.
6. **Save Settings:** Preserve your settings for future sessions using the `Save Settings` button.

## ⚙️ Configuration

The application uses a `config.ini` file to store your settings. This file is automatically created in the application directory when you save your settings for the first time.

## 🙏 Acknowledgments

This project wouldn't be possible without [whisper-standalone-win](https://github.com/Purfview/whisper-standalone-win). A big thank you to its developers for their exceptional work! 

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file for details.

## 📞 Contact

Have questions or suggestions? Don't hesitate to reach out to [Ognisty321](https://github.com/Ognisty321).
