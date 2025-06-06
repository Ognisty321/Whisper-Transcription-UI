import sys
import os
import subprocess
import logging
import configparser

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QComboBox,
    QLineEdit,
    QFileDialog,
    QListWidget,
    QProgressBar,
    QPushButton,
    QCheckBox,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QStyleFactory,
    QMessageBox,
    QFormLayout,
    QScrollArea
)
from PyQt6.QtCore import QThread, pyqtSignal, QByteArray
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

try:
    from PyQt6 import QtQuickControls2
    QtQuickControls2.QQuickStyle.setStyle("Material")
except ImportError:
    QApplication.setStyle(QStyleFactory.create('Fusion'))

SUPPORTED_LANGUAGES = [
    "Auto Detect", "Arabic", "Bengali", "Cantonese", "Catalan", "Chinese", "Czech", "Danish", "Dutch", "English",
    "Finnish", "French", "German", "Greek", "Haitian Creole", "Hebrew", "Hindi", "Hungarian", "Indonesian", "Italian",
    "Japanese", "Korean", "Norwegian", "Polish", "Portuguese", "Romanian", "Russian", "Slovak", "Slovenian", "Spanish",
    "Swedish", "Tagalog", "Thai", "Turkish", "Ukrainian", "Urdu", "Vietnamese"
]

WHISPER_MODELS = [
    "base", "base.en", "small", "small.en", "medium", "medium.en",
    "large", "large-v2", "large-v3", "large-v3-turbo", "distil-large-v2", "distil-large-v3", "distil-large-v3.5"
]

TASK_OPTIONS = ["transcribe", "translate"]
OUTPUT_FORMAT_OPTIONS = ["txt", "vtt", "srt", "tsv", "json", "all"]
VAD_METHOD_OPTIONS = [
    "silero_v3", "silero_v4", "silero_v5", "silero_v4_fw",
    "silero_v5_fw", "pyannote_v3", "pyannote_onnx_v3",
    "auditok", "webrtc"
]
COMPUTE_TYPE_OPTIONS = [
    "default", "auto", "int8", "int8_float16", "int8_float32", "int8_bfloat16",
    "int16", "float16", "float32", "bfloat16"
]
DIARIZE_METHOD_OPTIONS = ["pyannote_v3.0", "pyannote_v3.1", "reverb_v1", "reverb_v2"]
JAPANESE_STYLE_OPTIONS = ["Disabled", "blend", "kanji", "hiragana", "katakana"]

DEFAULT_VALUES = {
    "language": "Auto Detect",
    "model": "large-v2",
    "task": "transcribe",
    "output_dir": "",
    "vad_method": "pyannote_v3",
    "compute_type": "auto",
    "temperature": "0.0",
    "beam_size": "5",
    "best_of": "5",
    "mdx_chunk": "15",
    "voc_device": "cuda",
    "exe_path": ""
}

CONFIG_FILE = "config.ini"


class AppConfig:
    def __init__(self, config_file="config.ini", default_values=None):
        self.config_file = config_file
        self.default_values = default_values or {}
        self.config = configparser.ConfigParser()
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            self.config['Settings'] = self.default_values
            self.save_config()

    def save_config(self, widget_dict=None):
        if widget_dict:
            selected_formats = []
            for fmt in widget_dict['output_formats']:
                if widget_dict['output_formats'][fmt].isChecked():
                    selected_formats.append(fmt)
            output_format_str = " ".join(selected_formats) if selected_formats else "txt"

            # Validate ignore_dupe_prompt as int
            ignore_dupe_prompt_val = widget_dict['ignore_dupe_prompt'].text().strip()
            if ignore_dupe_prompt_val == '':
                ignore_dupe_prompt_val = '2'
            else:
                # Try convert to int, if fail default to '2'
                try:
                    int(ignore_dupe_prompt_val)
                except ValueError:
                    ignore_dupe_prompt_val = '2'

            self.config['Settings'] = {
                'language': widget_dict['language'].currentText(),
                'model': widget_dict['model'].currentText(),
                'task': widget_dict['task'].currentText(),
                'output_format': output_format_str,
                'output_dir': widget_dict['output_dir'].text(),
                'vad_filter': str(widget_dict['vad_filter'].isChecked()),
                'vad_method': widget_dict['vad_method'].currentText(),
                'word_timestamps': str(widget_dict['word_timestamps'].isChecked()),
                'temperature': widget_dict['temperature'].text(),
                'beam_size': widget_dict['beam_size'].text(),
                'best_of': widget_dict['best_of'].text(),
                'mdx_chunk': widget_dict['mdx_chunk'].text(),
                'voc_device': widget_dict['voc_device'].text(),
                'compute_type': widget_dict['compute_type'].currentText(),
                'ff_mdx_kim2': str(widget_dict['ff_mdx_kim2'].isChecked()),
                'enable_logging': str(widget_dict['enable_logging'].isChecked()),
                'sentence': str(widget_dict['sentence'].isChecked()),
                'exe_path': widget_dict['exe_path'].text() if 'exe_path' in widget_dict else self.default_values['exe_path'],
                'diarize': str(widget_dict['diarize'].isChecked()),
                'diarize_method': widget_dict['diarize_method'].currentText(),
                'num_speakers': widget_dict['num_speakers'].text(),
                'min_speakers': widget_dict['min_speakers'].text(),
                'max_speakers': widget_dict['max_speakers'].text(),
                'diarize_dump': widget_dict['diarize_dump'].text(),
                'hotwords': widget_dict['hotwords'].text(),
                'rehot': str(widget_dict['rehot'].isChecked()),
                'ignore_dupe_prompt': ignore_dupe_prompt_val,
                'multilingual': str(widget_dict['multilingual'].isChecked()),
                'batch_size': widget_dict['batch_size'].text(),
                'batched': str(widget_dict['batched'].isChecked()),
                'unmerged': str(widget_dict['unmerged'].isChecked()),
                'window_geometry': self.config['Settings'].get('window_geometry', ''),
                'ff_lc': str(widget_dict['ff_lc'].isChecked()),
                'ff_invert': str(widget_dict['ff_invert'].isChecked()),
                'return_embeddings': str(widget_dict['return_embeddings'].isChecked()),
                'diarize_only': str(widget_dict['diarize_only'].isChecked()),
                'japanese_style': widget_dict['japanese_style'].currentText(),
            }
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

    def get(self, section, option, fallback=None):
        return self.config.get(section, option, fallback=fallback)

    def get_boolean(self, section, option, fallback=None):
        return self.config.getboolean(section, option, fallback=fallback)


config = AppConfig(config_file=CONFIG_FILE, default_values={
    'language': DEFAULT_VALUES['language'],
    'model': DEFAULT_VALUES['model'],
    'task': DEFAULT_VALUES['task'],
    'output_format': 'txt',
    'output_dir': DEFAULT_VALUES['output_dir'],
    'vad_filter': 'True',
    'vad_method': DEFAULT_VALUES['vad_method'],
    'word_timestamps': 'True',
    'temperature': DEFAULT_VALUES['temperature'],
    'beam_size': DEFAULT_VALUES['beam_size'],
    'best_of': DEFAULT_VALUES['best_of'],
    'sentence': 'False',
    'ff_mdx_kim2': 'True',
    'mdx_chunk': DEFAULT_VALUES['mdx_chunk'],
    'voc_device': DEFAULT_VALUES['voc_device'],
    'compute_type': DEFAULT_VALUES['compute_type'],
    'enable_logging': 'True',
    'exe_path': DEFAULT_VALUES['exe_path'],
    'diarize': 'False',
    'diarize_method': DIARIZE_METHOD_OPTIONS[0],
    'num_speakers': '',
    'min_speakers': '',
    'max_speakers': '',
    'diarize_dump': '',
    'hotwords': '',
    'rehot': 'False',
    'ignore_dupe_prompt': '2',
    'multilingual': 'False',
    'batch_size': '',
    'batched': 'False',
    'unmerged': 'False',
    'window_geometry': '',
    'ff_lc': 'False',
    'ff_invert': 'False',
    'return_embeddings': 'False',
    'diarize_only': 'False',
    'japanese_style': 'Disabled',
})

if config.get_boolean('Settings', 'enable_logging', fallback=True):
    logging.basicConfig(filename='transcription.log', level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')


def enable_logging():
    return config.get_boolean('Settings', 'enable_logging', fallback=True)


def validate_file_extension(filename):
    valid_extensions = ('.wav', '.mp3', '.m4a', '.ogg', '.mp4',
                        '.mkv', '.avi', '.webm')
    return any(filename.lower().endswith(ext) for ext in valid_extensions)


def validate_numeric_input(value, min_value=None, max_value=None, allow_empty=True):
    if allow_empty and value.strip() == '':
        return True
    try:
        numeric_value = float(value)
        if min_value is not None and numeric_value < min_value:
            return False
        if max_value is not None and numeric_value > max_value:
            return False
        return True
    except ValueError:
        return False


def download_audio(url):
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)

    filename_template = os.path.join(output_dir, "%(id)s.%(ext)s")
    command = [
        "yt-dlp",
        "-f", "bestaudio",
        "--output", filename_template,
        url
    ]

    if enable_logging():
        logging.info(f"Executing yt-dlp command: {' '.join(command)}")

    result = subprocess.run(command, check=True, text=True, capture_output=True)
    if enable_logging():
        logging.info(f"yt-dlp stdout: {result.stdout}")
        logging.info(f"yt-dlp stderr: {result.stderr}")

    output_filename = None

    for line in result.stdout.splitlines():
        if "Destination:" in line:
            output_filename = line.split("Destination: ")[-1].strip()
            break

    if output_filename is None:
        for line in result.stdout.splitlines():
            if "[download]" in line and (".webm" in line or ".m4a" in line or ".mp3" in line):
                parts = line.split(']')
                if len(parts) > 1:
                    line_after_bracket = parts[1].strip()
                    possible_file = line_after_bracket.split(' ')[0].strip()
                    full_path = os.path.join(os.getcwd(), possible_file)
                    if os.path.exists(full_path):
                        output_filename = full_path
                        break
                    elif os.path.exists(possible_file):
                        output_filename = possible_file
                        break

    if output_filename is None:
        files_in_downloads = os.listdir(output_dir)
        if files_in_downloads:
            newest_file = max([os.path.join(output_dir, f) for f in files_in_downloads], key=os.path.getctime)
            if os.path.isfile(newest_file):
                output_filename = newest_file

    if output_filename is None or not os.path.isfile(output_filename):
        raise Exception("Failed to locate the downloaded file.")

    if enable_logging():
        logging.info(f"Downloaded file location: {output_filename}")

    return output_filename


class TranscriptionWorker(QThread):
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, file_list, widget_dict):
        super().__init__()
        self.file_list = file_list
        self.widget_dict = widget_dict

    def run(self):
        try:
            self.run_transcription()
        except Exception as e:
            self.error_occurred.emit(f"An unexpected error occurred: {e}")
            if enable_logging():
                logging.error(f"An unexpected error occurred during transcription: {e}")

    def run_transcription(self):
        if not self.file_list:
            self.error_occurred.emit("Please select at least one file or provide a link.")
            return

        language = self.widget_dict['language'].currentText()
        if language == "Auto Detect":
            language = None

        model = self.widget_dict['model'].currentText()
        task = self.widget_dict['task'].currentText()

        selected_formats = []
        for fmt, cb in self.widget_dict['output_formats'].items():
            if cb.isChecked():
                selected_formats.append(fmt)
        if not selected_formats:
            selected_formats = ["txt"]

        output_dir = self.widget_dict['output_dir'].text() or "output"
        exe_path = config.get('Settings', 'exe_path', fallback=DEFAULT_VALUES['exe_path']) or "faster-whisper-xxl.exe"

        ff_vocal_extract = self.widget_dict['ff_mdx_kim2'].isChecked()

        # Convert boolean QCheckBox to "True" or "False" for arguments that require a value
        # vad_filter expects True/False (not lowercased)
        vad_filter_val = "True" if self.widget_dict['vad_filter'].isChecked() else "False"
        vad_method = self.widget_dict['vad_method'].currentText() if self.widget_dict['vad_filter'].isChecked() else ""

        # word_timestamps expects True/False
        word_timestamps_val = "True" if self.widget_dict['word_timestamps'].isChecked() else "False"

        sentence = self.widget_dict['sentence'].isChecked()

        diarize = self.widget_dict['diarize'].isChecked()
        diarize_method = self.widget_dict['diarize_method'].currentText().strip()
        num_speakers = self.widget_dict['num_speakers'].text().strip()
        min_speakers = self.widget_dict['min_speakers'].text().strip()
        max_speakers = self.widget_dict['max_speakers'].text().strip()
        diarize_dump = self.widget_dict['diarize_dump'].text().strip()
        diarize_only = self.widget_dict['diarize_only'].isChecked()
        return_embeddings = self.widget_dict['return_embeddings'].isChecked()

        hotwords = self.widget_dict['hotwords'].text().strip()
        rehot = self.widget_dict['rehot'].isChecked()

        ignore_dupe_prompt_val = self.widget_dict['ignore_dupe_prompt'].text().strip()
        if ignore_dupe_prompt_val == '':
            ignore_dupe_prompt_val = '2'
        try:
            int(ignore_dupe_prompt_val)
        except ValueError:
            ignore_dupe_prompt_val = '2'

        # multilingual expects True/False
        multilingual_val = "True" if self.widget_dict['multilingual'].isChecked() else "False"

        batch_size = self.widget_dict['batch_size'].text().strip()
        batched = self.widget_dict['batched'].isChecked()
        unmerged = self.widget_dict['unmerged'].isChecked()

        temperature = self.widget_dict['temperature'].text()
        if not validate_numeric_input(temperature, 0.0, 1.0, allow_empty=False):
            self.error_occurred.emit("Temperature must be a number between 0.0 and 1.0.")
            return
        temperature = str(float(temperature))

        beam_size = self.widget_dict['beam_size'].text()
        if not validate_numeric_input(beam_size, 1, 100, allow_empty=False):
            self.error_occurred.emit("Beam size must be an integer between 1 and 100.")
            return

        best_of = self.widget_dict['best_of'].text()
        if not validate_numeric_input(best_of, 1, 100, allow_empty=False):
            self.error_occurred.emit("Best of must be an integer between 1 and 100.")
            return

        mdx_chunk = self.widget_dict['mdx_chunk'].text()
        if not validate_numeric_input(mdx_chunk, 1, 100, allow_empty=False):
            self.error_occurred.emit("Vocal extraction chunk must be an integer between 1 and 100.")
            return

        voc_device = self.widget_dict['voc_device'].text()
        compute_type = self.widget_dict['compute_type'].currentText()

        # New options
        ff_lc = self.widget_dict['ff_lc'].isChecked()
        ff_invert = self.widget_dict['ff_invert'].isChecked()
        japanese_style = self.widget_dict['japanese_style'].currentText()

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        total_files = len(self.file_list)
        self.progress_updated.emit(0, f"Progress: 0/{total_files}")

        for index, file_path in enumerate(self.file_list, start=1):
            if file_path.startswith(("http://", "https://")):
                try:
                    filename = download_audio(file_path)
                except Exception as e:
                    self.error_occurred.emit(f"Failed to download from {file_path}: {e}")
                    if enable_logging():
                        logging.error(f"Failed to download from {file_path}: {e}")
                    continue
            else:
                filename = file_path

            command = [
                exe_path,
                filename,
                "--model", model,
            ]
            if task != "transcribe":
                command.extend(["--task", task])

            command.extend(["--output_dir", output_dir])

            for fmt in selected_formats:
                command.extend(["--output_format", fmt])

            command.extend(["--compute_type", compute_type])

            if language:
                command.extend(["--language", language])

            if ff_vocal_extract:
                command.extend(["--ff_vocal_extract", "mdx_kim2", "--mdx_chunk", mdx_chunk, "--voc_device", voc_device])
            
            if ff_lc:
                command.append("--ff_lc")
            if ff_invert:
                command.append("--ff_invert")
            if japanese_style != "Disabled":
                command.extend(["--japanese", japanese_style])

            # vad_filter with True/False
            command.extend(["--vad_filter", vad_filter_val])
            if self.widget_dict['vad_filter'].isChecked() and vad_method:
                command.extend(["--vad_method", vad_method])

            # word_timestamps with True/False
            command.extend(["--word_timestamps", word_timestamps_val])

            if sentence:
                command.append("--sentence")

            command.extend(["--temperature", temperature])
            command.extend(["--beam_size", beam_size])
            command.extend(["--best_of", best_of])

            if diarize:
                command.extend(["--diarize", diarize_method])
                if num_speakers:
                    command.extend(["--num_speakers", num_speakers])
                if min_speakers:
                    command.extend(["--min_speakers", min_speakers])
                if max_speakers:
                    command.extend(["--max_speakers", max_speakers])
                if diarize_dump:
                    command.append("--diarize_dump")
                if return_embeddings:
                    command.append("--return_embeddings")
                if diarize_only:
                    command.append("--diarize_only")

            if hotwords:
                command.extend(["--hotwords", hotwords])
            if rehot:
                command.append("--rehot")

            # ignore_dupe_prompt requires int
            command.extend(["--ignore_dupe_prompt", ignore_dupe_prompt_val])

            # multilingual True/False
            command.extend(["--multilingual", multilingual_val])

            if batch_size:
                command.extend(["--batch_size", batch_size])
            if batched:
                command.append("--batched")
            if unmerged:
                command.append("--unmerged")

            if enable_logging():
                logging.info("Selected Options:")
                logging.info(f"  File: {filename}")
                logging.info(f"  Language: {language}")
                logging.info(f"  Model: {model}")
                logging.info(f"  Task: {task}")
                logging.info(f"  Output Formats: {' '.join(selected_formats)}")
                logging.info(f"  Output Directory: {output_dir}")
                logging.info(f"  Vocal Extraction: {ff_vocal_extract}")
                logging.info(f"  Vocal Extraction Chunk: {mdx_chunk}")
                logging.info(f"  Vocal Extraction Device: {voc_device}")
                logging.info(f"  Use Left Channel Only: {ff_lc}")
                logging.info(f"  Invert Polarity: {ff_invert}")
                logging.info(f"  Japanese Style: {japanese_style}")
                logging.info(f"  VAD Filter: {vad_filter_val}")
                logging.info(f"  VAD Method: {vad_method}")
                logging.info(f"  Word Timestamps: {word_timestamps_val}")
                logging.info(f"  Sentence: {sentence}")
                logging.info(f"  Temperature: {temperature}")
                logging.info(f"  Beam Size: {beam_size}")
                logging.info(f"  Best Of: {best_of}")
                logging.info(f"  Compute Type: {compute_type}")
                logging.info(f"  Diarize: {diarize}")
                logging.info(f"  Diarize Method: {diarize_method}")
                logging.info(f"  Num Speakers: {num_speakers}")
                logging.info(f"  Min Speakers: {min_speakers}")
                logging.info(f"  Max Speakers: {max_speakers}")
                logging.info(f"  Diarize Dump: {diarize_dump}")
                logging.info(f"  Diarize Only: {diarize_only}")
                logging.info(f"  Return Embeddings: {return_embeddings}")
                logging.info(f"  Hotwords: {hotwords}")
                logging.info(f"  Rehot: {rehot}")
                logging.info(f"  Ignore Dupe Prompt: {ignore_dupe_prompt_val}")
                logging.info(f"  Multilingual: {multilingual_val}")
                logging.info(f"  Batch Size: {batch_size}")
                logging.info(f"  Batched: {batched}")
                logging.info(f"  Unmerged: {unmerged}")
                logging.info("Command:")
                logging.info(" ".join(command))

            try:
                subprocess.run(command, shell=False, check=True)
                progress = int((index / total_files) * 100)
                self.progress_updated.emit(progress, f"Progress: {index}/{total_files}")
                if enable_logging():
                    logging.info(f"Transcription complete for {filename}.")
            except subprocess.CalledProcessError as e:
                self.error_occurred.emit(f"An error occurred during transcription of {filename}: {e}")
                if enable_logging():
                    logging.error(f"An error occurred during transcription of {filename}: {e}")

        self.finished.emit()


class Expander(QWidget):
    def __init__(self, label, target):
        super().__init__()
        self.label = label
        self.target = target
        self.collapsed = True
        self.init_ui()
        self.target.setVisible(False)
        self.update_header_label()

    def init_ui(self):
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.header = QLabel()
        self.header.setStyleSheet("QLabel {font-weight: bold;}")
        self.header.mouseReleaseEvent = self.expand_collapse
        self.layout.addWidget(self.header)
        self.layout.addWidget(self.target)
        self.setLayout(self.layout)
        self.update_header_label()

    def expand_collapse(self, event):
        self.collapsed = not self.collapsed
        self.target.setVisible(not self.collapsed)
        self.update_header_label()

    def update_header_label(self):
        if self.collapsed:
            self.header.setText(self.label + " ▼")
        else:
            self.header.setText(self.label + " ▲")


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Whisper Transcription App")
        self.resize(600, 800)

        self.widget_dict = {}
        self.create_widgets()
        self.create_layout()
        self.load_settings()
        self.setAcceptDrops(True)
        self.load_window_geometry()

    def closeEvent(self, event):
        self.save_window_geometry()
        event.accept()

    def load_window_geometry(self):
        geometry = config.get('Settings', 'window_geometry', fallback='')
        if geometry:
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode('utf-8')))

    def save_window_geometry(self):
        config.config['Settings']['window_geometry'] = self.saveGeometry().toBase64().data().decode('utf-8')
        config.save_config()

    def save_settings(self):
        config.save_config(self.widget_dict)
        self.save_window_geometry()

    def create_widgets(self):
        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_files)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_files)
        self.file_entry = QLineEdit()
        self.file_entry.setPlaceholderText("Enter file path or URL")
        self.add_file_button = QPushButton("Add")
        self.add_file_button.clicked.connect(self.add_file_from_entry)

        self.widget_dict['language'] = QComboBox()
        self.widget_dict['language'].addItems(SUPPORTED_LANGUAGES)
        self.widget_dict['model'] = QComboBox()
        self.widget_dict['model'].addItems(WHISPER_MODELS)
        self.widget_dict['task'] = QComboBox()
        self.widget_dict['task'].addItems(TASK_OPTIONS)

        self.widget_dict['output_formats'] = {}
        for fmt in OUTPUT_FORMAT_OPTIONS:
            cb = QCheckBox(fmt)
            self.widget_dict['output_formats'][fmt] = cb

        self.widget_dict['output_dir'] = QLineEdit()
        self.browse_output_dir_button = QPushButton("Browse")
        self.browse_output_dir_button.clicked.connect(self.browse_output_dir)

        self.widget_dict['ff_mdx_kim2'] = QCheckBox("Enable Vocal Extraction (Kim Vocal 2)")
        self.widget_dict['vad_filter'] = QCheckBox("Enable VAD Filter")
        self.widget_dict['vad_method'] = QComboBox()
        self.widget_dict['vad_method'].addItems(VAD_METHOD_OPTIONS)
        self.widget_dict['word_timestamps'] = QCheckBox("Enable Word Timestamps")
        self.widget_dict['sentence'] = QCheckBox("Split into sentences")
        self.widget_dict['compute_type'] = QComboBox()
        self.widget_dict['compute_type'].addItems(COMPUTE_TYPE_OPTIONS)
        self.widget_dict['temperature'] = QLineEdit()
        self.widget_dict['beam_size'] = QLineEdit()
        self.widget_dict['best_of'] = QLineEdit()
        self.widget_dict['mdx_chunk'] = QLineEdit()
        self.widget_dict['voc_device'] = QLineEdit()
        self.widget_dict['enable_logging'] = QCheckBox("Enable Logging")
        self.widget_dict['ff_lc'] = QCheckBox("Use Left Channel Only (--ff_lc)")
        self.widget_dict['ff_invert'] = QCheckBox("Invert Polarity & Mix to Mono (--ff_invert)")
        self.widget_dict['japanese_style'] = QComboBox()
        self.widget_dict['japanese_style'].addItems(JAPANESE_STYLE_OPTIONS)

        self.widget_dict['diarize'] = QCheckBox("Enable Diarization")
        self.widget_dict['diarize_method'] = QComboBox()
        self.widget_dict['diarize_method'].addItems(DIARIZE_METHOD_OPTIONS)
        self.widget_dict['num_speakers'] = QLineEdit()
        self.widget_dict['min_speakers'] = QLineEdit()
        self.widget_dict['max_speakers'] = QLineEdit()
        self.widget_dict['diarize_dump'] = QLineEdit()
        self.widget_dict['diarize_only'] = QCheckBox("Diarize Only (no transcription)")
        self.widget_dict['return_embeddings'] = QCheckBox("Return Diarization Embeddings")
        self.widget_dict['hotwords'] = QLineEdit()
        self.widget_dict['rehot'] = QCheckBox("Re-Hotwords")

        self.widget_dict['ignore_dupe_prompt'] = QLineEdit()
        self.widget_dict['ignore_dupe_prompt'].setPlaceholderText("Integer (default 2)")

        self.widget_dict['multilingual'] = QCheckBox("Multilingual")
        self.widget_dict['batch_size'] = QLineEdit()
        self.widget_dict['batched'] = QCheckBox("Batched")
        self.widget_dict['unmerged'] = QCheckBox("Unmerged")

        self.widget_dict['exe_path'] = QLineEdit()
        self.widget_dict['exe_path'].setPlaceholderText("Path to whisper-standalone exe (optional)")

        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("Progress: 0/0")
        self.transcribe_button = QPushButton("Start")
        self.transcribe_button.clicked.connect(self.start_transcription)
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.save_settings)

    def create_layout(self):
        main_layout = QVBoxLayout()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)

        file_selection_layout = QGridLayout()
        file_selection_layout.addWidget(QLabel("Audio/Video Files:"), 0, 0, 1, 2)
        file_selection_layout.addWidget(self.file_list_widget, 1, 0, 1, 2)
        file_selection_layout.addWidget(self.file_entry, 2, 0)
        file_selection_layout.addWidget(self.add_file_button, 2, 1)
        file_selection_layout.addWidget(self.browse_button, 3, 0)
        file_selection_layout.addWidget(self.clear_button, 3, 1)
        container_layout.addLayout(file_selection_layout)

        options_group_box = QGroupBox("Basic Options")
        options_layout = QFormLayout()
        options_layout.addRow("Language:", self.widget_dict['language'])
        options_layout.addRow("Model:", self.widget_dict['model'])
        options_layout.addRow("Task:", self.widget_dict['task'])

        output_format_layout = QHBoxLayout()
        for fmt, cb in self.widget_dict['output_formats'].items():
            output_format_layout.addWidget(cb)
        fmt_box = QGroupBox("Output Formats (Select multiple)")
        fmt_box.setLayout(output_format_layout)
        options_layout.addRow(fmt_box)

        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(self.widget_dict['output_dir'])
        output_dir_layout.addWidget(self.browse_output_dir_button)
        options_layout.addRow("Output Directory:", output_dir_layout)
        options_group_box.setLayout(options_layout)
        container_layout.addWidget(options_group_box)

        advanced_widget = QWidget()
        advanced_form = QFormLayout(advanced_widget)
        advanced_form.addRow(self.widget_dict['ff_mdx_kim2'])
        advanced_form.addRow("Vocal Extraction Chunk (s):", self.widget_dict['mdx_chunk'])
        advanced_form.addRow("Vocal Extraction Device:", self.widget_dict['voc_device'])
        advanced_form.addRow(self.widget_dict['ff_lc'])
        advanced_form.addRow(self.widget_dict['ff_invert'])

        adv_vad_layout = QHBoxLayout()
        adv_vad_layout.addWidget(self.widget_dict['vad_filter'])
        adv_vad_layout.addWidget(QLabel("Method:"))
        adv_vad_layout.addWidget(self.widget_dict['vad_method'])
        advanced_form.addRow("VAD:", adv_vad_layout)

        advanced_form.addRow(self.widget_dict['word_timestamps'])
        advanced_form.addRow(self.widget_dict['sentence'])
        advanced_form.addRow("Compute Type:", self.widget_dict['compute_type'])
        advanced_form.addRow("Temperature:", self.widget_dict['temperature'])
        advanced_form.addRow("Beam Size:", self.widget_dict['beam_size'])
        advanced_form.addRow("Best Of:", self.widget_dict['best_of'])
        advanced_form.addRow("Japanese Writing Style:", self.widget_dict['japanese_style'])
        advanced_form.addRow(self.widget_dict['enable_logging'])
        advanced_form.addRow("Executable Path:", self.widget_dict['exe_path'])

        diarize_box = QGroupBox("Diarization & Additional Options")
        diarize_layout = QFormLayout(diarize_box)
        diarize_layout.addRow(self.widget_dict['diarize'])
        diarize_layout.addRow("Diarize Method:", self.widget_dict['diarize_method'])
        diarize_layout.addRow(self.widget_dict['diarize_only'])
        diarize_layout.addRow(self.widget_dict['return_embeddings'])
        diarize_layout.addRow("Num Speakers:", self.widget_dict['num_speakers'])
        diarize_layout.addRow("Min Speakers:", self.widget_dict['min_speakers'])
        diarize_layout.addRow("Max Speakers:", self.widget_dict['max_speakers'])
        diarize_layout.addRow("Diarize Dump:", self.widget_dict['diarize_dump'])
        diarize_layout.addRow("Hotwords:", self.widget_dict['hotwords'])
        diarize_layout.addRow(self.widget_dict['rehot'])
        diarize_layout.addRow("Ignore Dupe Prompt (int):", self.widget_dict['ignore_dupe_prompt'])
        diarize_layout.addRow(self.widget_dict['multilingual'])
        diarize_layout.addRow("Batch Size:", self.widget_dict['batch_size'])
        diarize_layout.addRow(self.widget_dict['batched'])
        diarize_layout.addRow(self.widget_dict['unmerged'])

        advanced_expander = Expander("Advanced & Additional Options", QWidget())
        adv_inner_layout = QVBoxLayout(advanced_expander.target)
        adv_inner_layout.addWidget(advanced_widget)
        adv_inner_layout.addWidget(diarize_box)
        container_layout.addWidget(advanced_expander)

        progress_layout = QHBoxLayout()
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        container_layout.addLayout(progress_layout)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.transcribe_button)
        button_layout.addWidget(self.save_button)
        container_layout.addLayout(button_layout)

        scroll_area.setWidget(container_widget)
        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)

    def browse_files(self):
        filenames, _ = QFileDialog.getOpenFileNames(
            self, "Select Audio/Video Files", "/",
            "All Supported Files (*.wav *.mp3 *.m4a *.ogg *.mp4 *.mkv *.avi *.webm);;All Files (*.*)"
        )
        self.file_list_widget.addItems(filenames)

    def browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        self.widget_dict['output_dir'].setText(directory)

    def add_file_from_entry(self):
        file_path = self.file_entry.text().strip()
        if file_path:
            if validate_file_extension(file_path) or file_path.startswith(("http://", "https://")):
                self.file_list_widget.addItem(file_path)
                self.file_entry.clear()
            else:
                QMessageBox.warning(self, "Error", f"Invalid file path or unsupported file extension: {file_path}")
        else:
            QMessageBox.warning(self, "Error", "Input cannot be empty.")

    def clear_files(self):
        self.file_list_widget.clear()

    def load_settings(self):
        self.widget_dict['language'].setCurrentText(config.get('Settings', 'language', fallback=DEFAULT_VALUES['language']))
        self.widget_dict['model'].setCurrentText(config.get('Settings', 'model', fallback=DEFAULT_VALUES['model']))
        self.widget_dict['task'].setCurrentText(config.get('Settings', 'task', fallback=DEFAULT_VALUES['task']))

        saved_output_formats = config.get('Settings', 'output_format', fallback='txt').split()
        for fmt in self.widget_dict['output_formats']:
            self.widget_dict['output_formats'][fmt].setChecked(fmt in saved_output_formats)

        self.widget_dict['output_dir'].setText(config.get('Settings', 'output_dir', fallback=''))
        self.widget_dict['ff_mdx_kim2'].setChecked(config.get_boolean('Settings', 'ff_mdx_kim2', fallback=True))
        self.widget_dict['vad_filter'].setChecked(config.get_boolean('Settings', 'vad_filter', fallback=True))
        self.widget_dict['vad_method'].setCurrentText(config.get('Settings', 'vad_method', fallback=DEFAULT_VALUES['vad_method']))
        self.widget_dict['word_timestamps'].setChecked(config.get_boolean('Settings', 'word_timestamps', fallback=True))
        self.widget_dict['temperature'].setText(config.get('Settings', 'temperature', fallback=DEFAULT_VALUES['temperature']))
        self.widget_dict['beam_size'].setText(config.get('Settings', 'beam_size', fallback=DEFAULT_VALUES['beam_size']))
        self.widget_dict['best_of'].setText(config.get('Settings', 'best_of', fallback=DEFAULT_VALUES['best_of']))
        self.widget_dict['mdx_chunk'].setText(config.get('Settings', 'mdx_chunk', fallback=DEFAULT_VALUES['mdx_chunk']))
        self.widget_dict['voc_device'].setText(config.get('Settings', 'voc_device', fallback=DEFAULT_VALUES['voc_device']))
        self.widget_dict['compute_type'].setCurrentText(config.get('Settings', 'compute_type', fallback=DEFAULT_VALUES['compute_type']))
        self.widget_dict['enable_logging'].setChecked(config.get_boolean('Settings', 'enable_logging', fallback=True))
        self.widget_dict['sentence'].setChecked(config.get_boolean('Settings', 'sentence', fallback=False))
        self.widget_dict['exe_path'].setText(config.get('Settings', 'exe_path', fallback=DEFAULT_VALUES['exe_path']))
        self.widget_dict['ff_lc'].setChecked(config.get_boolean('Settings', 'ff_lc', fallback=False))
        self.widget_dict['ff_invert'].setChecked(config.get_boolean('Settings', 'ff_invert', fallback=False))
        self.widget_dict['japanese_style'].setCurrentText(config.get('Settings', 'japanese_style', fallback='Disabled'))

        self.widget_dict['diarize'].setChecked(config.get_boolean('Settings', 'diarize', fallback=False))
        self.widget_dict['diarize_method'].setCurrentText(config.get('Settings', 'diarize_method', fallback=DIARIZE_METHOD_OPTIONS[0]))
        self.widget_dict['diarize_only'].setChecked(config.get_boolean('Settings', 'diarize_only', fallback=False))
        self.widget_dict['return_embeddings'].setChecked(config.get_boolean('Settings', 'return_embeddings', fallback=False))
        self.widget_dict['num_speakers'].setText(config.get('Settings', 'num_speakers', fallback=''))
        self.widget_dict['min_speakers'].setText(config.get('Settings', 'min_speakers', fallback=''))
        self.widget_dict['max_speakers'].setText(config.get('Settings', 'max_speakers', fallback=''))
        self.widget_dict['diarize_dump'].setText(config.get('Settings', 'diarize_dump', fallback=''))
        self.widget_dict['hotwords'].setText(config.get('Settings', 'hotwords', fallback=''))
        self.widget_dict['rehot'].setChecked(config.get_boolean('Settings', 'rehot', fallback=False))

        ignore_val = config.get('Settings', 'ignore_dupe_prompt', fallback='2')
        try:
            int(ignore_val)
        except ValueError:
            ignore_val = '2'
        self.widget_dict['ignore_dupe_prompt'].setText(ignore_val)

        multilingual_val = config.get('Settings', 'multilingual', fallback='False')
        self.widget_dict['multilingual'].setChecked(multilingual_val.lower() == 'true')

        self.widget_dict['batch_size'].setText(config.get('Settings', 'batch_size', fallback=''))
        self.widget_dict['batched'].setChecked(config.get_boolean('Settings', 'batched', fallback=False))
        self.widget_dict['unmerged'].setChecked(config.get_boolean('Settings', 'unmerged', fallback=False))

    def start_transcription(self):
        file_list = [self.file_list_widget.item(i).text() for i in range(self.file_list_widget.count())]

        self.transcribe_button.setEnabled(False)
        self.save_button.setEnabled(False)

        self.transcription_worker = TranscriptionWorker(file_list, self.widget_dict)
        self.transcription_worker.progress_updated.connect(self.update_progress)
        self.transcription_worker.finished.connect(self.transcription_finished)
        self.transcription_worker.error_occurred.connect(self.show_error_message)
        self.transcription_worker.start()

    def update_progress(self, progress, message):
        self.progress_bar.setValue(progress)
        self.progress_label.setText(message)

    def transcription_finished(self):
        QMessageBox.information(self, "Success", "Transcription completed for all files!")
        if enable_logging():
            logging.info("Transcription completed for all files.")
        self.reset_progress()
        self.transcribe_button.setEnabled(True)
        self.save_button.setEnabled(True)

    def show_error_message(self, error_message):
        QMessageBox.critical(self, "Error", error_message)
        if enable_logging():
            logging.error(error_message)
        self.reset_progress()
        self.transcribe_button.setEnabled(True)
        self.save_button.setEnabled(True)

    def reset_progress(self):
        self.progress_bar.setValue(0)
        self.progress_label.setText("Progress: 0/0")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if os.path.isfile(file_path) and validate_file_extension(file_path):
                    self.file_list_widget.addItem(file_path)
        else:
            event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())