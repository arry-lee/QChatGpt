import ctypes
import glob
import os
import platform
import shutil
from functools import partial
import qdarkstyle

this_file = os.path.realpath(__file__)
wd = os.path.dirname(this_file)
if os.getcwd() != wd:
    os.chdir(wd)
if not os.path.isfile("config.py"):
    open("config.py", "a", encoding="utf-8").close()
from configDefault import *
import re, sqlite3, webbrowser, sys, pprint
from shutil import copyfile
from datetime import datetime
from util.worker import ChatGPTResponse
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import (
    QStandardItemModel,
    QStandardItem,
    QGuiApplication,
    QAction,
    QIcon,
    QFontMetrics,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QCompleter,
    QMenu,
    QSystemTrayIcon,
    QApplication,
    QMainWindow,
    QTextEdit,
    QWidget,
    QFileDialog,
    QLabel,
    QMessageBox,
    QCheckBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QListView,
    QHBoxLayout,
    QVBoxLayout,
    QLineEdit,
    QSplitter,
    QComboBox,
)


class Database:
    def __init__(self, filePath=""):
        def regexp(expr, item):
            reg = re.compile(expr, flags=re.IGNORECASE)
            return reg.search(item) is not None

        defaultFilePath = (
            config.chatGPTApiLastChatDatabase
            if config.chatGPTApiLastChatDatabase
            and os.path.isfile(config.chatGPTApiLastChatDatabase)
            else os.path.join(wd, "chats", "default.chat")
        )
        self.filePath = filePath if filePath else defaultFilePath
        self.connection = sqlite3.connect(self.filePath)
        self.connection.create_function("REGEXP", 2, regexp)
        self.cursor = self.connection.cursor()
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS data (id TEXT PRIMARY KEY, title TEXT, content TEXT)"
        )
        self.connection.commit()

    def insert(self, id, title, content):
        self.cursor.execute("SELECT * FROM data WHERE id = ?", (id,))
        existing_data = self.cursor.fetchone()
        if existing_data:
            if existing_data[1] == title and existing_data[2] == content:
                return
            else:
                self.cursor.execute(
                    "UPDATE data SET title = ?, content = ? WHERE id = ?",
                    (title, content, id),
                )
                self.connection.commit()
        else:
            self.cursor.execute(
                "INSERT INTO data (id, title, content) VALUES (?, ?, ?)",
                (id, title, content),
            )
            self.connection.commit()

    def search(self, title, content):
        if config.regexpSearchEnabled:
            self.cursor.execute(
                "SELECT * FROM data WHERE title REGEXP ? AND content REGEXP ?",
                (title, content),
            )
        else:
            self.cursor.execute(
                "SELECT * FROM data WHERE title LIKE ? AND content LIKE ?",
                ("%{}%".format(title), "%{}%".format(content)),
            )
        return self.cursor.fetchall()

    def delete(self, id):
        self.cursor.execute("DELETE FROM data WHERE id = ?", (id,))
        self.connection.commit()

    def clear(self):
        self.cursor.execute("DELETE FROM data")
        self.connection.commit()


class QChatGpt(QWidget):
    def __init__(self, parent):
        super().__init__()
        config.chatGPTApi = self
        self.parent = parent
        self.setWindowTitle("ChatGPT-GUI")
        self.setupVariables()
        self.setupUI()
        self.loadData()
        self.newData()

    def openDatabase(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        (filePath, _) = QFileDialog.getOpenFileName(
            self,
            "Open Database",
            os.path.join(wd, "chats", "default.chat"),
            "ChatGPT-GUI Database (*.chat)",
            options=options,
        )
        self.database = Database(filePath)
        self.loadData()
        self.updateTitle(filePath)
        self.newData()

    def newDatabase(self, copyExistingDatabase=False):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        (filePath, _) = QFileDialog.getSaveFileName(
            self,
            "New Database",
            os.path.join(
                wd,
                "chats",
                self.database.filePath if copyExistingDatabase else "new.chat",
            ),
            "ChatGPT-GUI Database (*.chat)",
            options=options,
        )
        if filePath:
            if not filePath.endswith(".chat"):
                filePath += ".chat"
            if copyExistingDatabase and os.path.abspath(filePath) == os.path.abspath(
                self.database.filePath
            ):
                return
            if os.path.exists(filePath):
                msgBox = QMessageBox()
                msgBox.setWindowTitle("Confirm overwrite")
                msgBox.setText(
                    f"The file {filePath} already exists. Do you want to replace it?"
                )
                msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msgBox.setDefaultButton(QMessageBox.No)
                if msgBox.exec() == QMessageBox.No:
                    return
                else:
                    os.remove(filePath)
            if copyExistingDatabase:
                shutil.copy(self.database.filePath, filePath)
            self.database = Database(filePath)
            self.loadData()
            self.updateTitle(filePath)
            self.newData()

    def updateTitle(self, filePath=""):
        if not filePath:
            filePath = self.database.filePath
        config.chatGPTApiLastChatDatabase = filePath
        basename = os.path.basename(filePath)
        self.parent.setWindowTitle(f"ChatGPT-GUI - {basename}")

    def setupVariables(self):
        self.busyLoading = False
        self.contentID = ""
        self.database = Database()
        self.updateTitle()
        self.data_list = []

    def setupUI(self):
        layout000 = QHBoxLayout()
        self.setLayout(layout000)
        widgetLt = QWidget()
        layout000Lt = QVBoxLayout()
        widgetLt.setLayout(layout000Lt)
        widgetRt = QWidget()
        layout000Rt = QVBoxLayout()
        widgetRt.setLayout(layout000Rt)
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(widgetLt)
        splitter.addWidget(widgetRt)
        splitter.setSizes([25, 75])
        splitter.setHandleWidth(1)
        layout000.addWidget(splitter)
        self.userInput = QLineEdit()
        self.userInput.setPlaceholderText(config.thisTranslation["messageHere"])
        self.userInput.mousePressEvent = lambda _: self.userInput.selectAll()
        self.userInput.setClearButtonEnabled(True)
        self.userInputMultiline = QPlainTextEdit()
        self.userInputMultiline.setPlaceholderText(
            config.thisTranslation["messageHere"]
        )
        self.contentView = QPlainTextEdit()
        self.contentView.setReadOnly(True)
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 0)
        self.multilineButton = QPushButton("+")
        font_metrics = QFontMetrics(self.multilineButton.font())
        text_rect = font_metrics.boundingRect(self.multilineButton.text())
        button_width = text_rect.width() + 20
        button_height = text_rect.height() + 10
        self.multilineButton.setFixedSize(button_width, button_height)
        self.sendButton = QPushButton(config.thisTranslation["send"])
        self.newButton = QPushButton(config.thisTranslation["new"])
        saveButton = QPushButton(config.thisTranslation["save"])
        self.editableCheckbox = QCheckBox(config.thisTranslation["editable"])
        self.editableCheckbox.setCheckState(Qt.Unchecked)
        self.fontSize = QComboBox()
        self.fontSize.addItems([str(i) for i in range(1, 51)])
        self.fontSize.setCurrentIndex(config.fontSize - 1)
        promptLayout = QHBoxLayout()
        userInputLayout = QVBoxLayout()
        userInputLayout.addWidget(self.userInput)
        userInputLayout.addWidget(self.userInputMultiline)
        self.userInputMultiline.hide()
        promptLayout.addLayout(userInputLayout)
        promptLayout.addWidget(self.multilineButton)
        promptLayout.addWidget(self.sendButton)
        layout000Rt.addWidget(self.contentView)
        layout000Rt.addWidget(self.progressBar)
        layout000Rt.addLayout(promptLayout)
        self.progressBar.hide()
        rtButtonLayout = QHBoxLayout()
        rtButtonLayout.addWidget(self.newButton)
        rtButtonLayout.addWidget(saveButton)
        helpButton = QPushButton(config.thisTranslation["help"])
        self.listView = QListView()
        self.listModel = QStandardItemModel()
        self.listView.setModel(self.listModel)
        removeButton = QPushButton(config.thisTranslation["remove"])
        clearAllButton = QPushButton(config.thisTranslation["clearAll"])
        layout000Lt.addWidget(self.listView)
        ltButtonLayout = QHBoxLayout()
        ltButtonLayout.addWidget(removeButton)
        ltButtonLayout.addWidget(clearAllButton)
        layout000Lt.addLayout(ltButtonLayout)
        layout000Lt.addLayout(rtButtonLayout)
        self.userInput.returnPressed.connect(self.sendMessage)
        helpButton.clicked.connect(
            lambda: webbrowser.open(
                "https://github.com/arry-lee/QChatGpt/blob/main/README.md"
            )
        )
        self.multilineButton.clicked.connect(self.multilineButtonClicked)
        self.sendButton.clicked.connect(self.sendMessage)
        saveButton.clicked.connect(self.saveData)
        self.newButton.clicked.connect(self.newData)
        self.listView.clicked.connect(self.selectData)
        clearAllButton.clicked.connect(self.clearData)
        removeButton.clicked.connect(self.removeData)
        self.editableCheckbox.stateChanged.connect(self.toggleEditable)
        self.fontSize.currentIndexChanged.connect(self.setFontSize)
        self.setFontSize()

    def setFontSize(self, index=None):
        if index is not None:
            config.fontSize = index + 1
        font = self.contentView.font()
        font.setPointSize(config.fontSize)
        self.contentView.setFont(font)
        font = self.listView.font()
        font.setPointSize(config.fontSize)
        self.listView.setFont(font)

    def multilineButtonClicked(self):
        if self.userInput.isVisible():
            self.userInput.hide()
            self.userInputMultiline.setPlainText(self.userInput.text())
            self.userInputMultiline.show()
            self.multilineButton.setText("-")
        else:
            self.userInputMultiline.hide()
            self.userInput.setText(self.userInputMultiline.toPlainText())
            self.userInput.show()
            self.multilineButton.setText("+")
        self.setUserInputFocus()

    def setUserInputFocus(self):
        self.userInput.setFocus() if self.userInput.isVisible() else self.userInputMultiline.setFocus()

    def toggleEditable(self, state):
        self.contentView.setReadOnly(not state)

    def removeData(self):
        index = self.listView.selectedIndexes()
        if not index:
            return
        confirm = QMessageBox.question(
            self,
            config.thisTranslation["remove"],
            config.thisTranslation["areyousure"],
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            item = index[0]
            data = item.data(Qt.UserRole)
            self.database.delete(data[0])
            self.loadData()
            self.newData()

    def clearData(self):
        confirm = QMessageBox.question(
            self,
            config.thisTranslation["clearAll"],
            config.thisTranslation["areyousure"],
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.database.clear()
            self.loadData()

    def saveData(self):
        text = self.contentView.toPlainText().strip()
        if text:
            lines = text.split("\n")
            if not self.contentID:
                self.contentID = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            title = re.sub("^>>> ", "", lines[0][:50])
            content = text
            self.database.insert(self.contentID, title, content)
            self.loadData()

    def loadData(self):
        self.data_list = self.database.search("", "")
        if self.data_list:
            self.data_list.reverse()
        self.listModel.clear()
        for data in self.data_list:
            item = QStandardItem(data[1])
            item.setToolTip(data[0])
            item.setData(data, Qt.UserRole)
            self.listModel.appendRow(item)

    def newData(self):
        if not self.busyLoading:
            self.contentID = ""
            self.setUserInputFocus()

    def selectData(self, index):
        if not self.busyLoading:
            data = index.data(Qt.UserRole)
            self.contentID = data[0]
            content = data[2]
            self.contentView.setPlainText(content)
            self.setUserInputFocus()

    def printData(self):
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.Accepted:
            document = QTextDocument()
            document.setPlainText(self.contentView.toPlainText())
            document.print_(printer)

    def getContext(self):
        if not config.chatGPTApiPredefinedContext in config.predefinedContexts:
            config.chatGPTApiPredefinedContext = "[none]"
        if config.chatGPTApiPredefinedContext == "[none]":
            context = ""
        elif config.chatGPTApiPredefinedContext == "[custom]":
            context = config.chatGPTApiContext
        else:
            context = config.predefinedContexts[config.chatGPTApiPredefinedContext]
        return context

    def getMessages(self, userInput):
        return userInput

    def print(self, text):
        self.contentView.appendPlainText(
            f"\n{text}" if self.contentView.toPlainText() else text
        )
        self.contentView.setPlainText(
            re.sub("\n\n[\n]+?([^\n])", "\\n\\n\\1", self.contentView.toPlainText())
        )

    def printStream(self, text):
        for t in config.chatGPTTransformers:
            text = t(text)
        self.contentView.setPlainText(self.contentView.toPlainText() + text)
        if config.chatGPTApiAutoScrolling:
            contentScrollBar = self.contentView.verticalScrollBar()
            contentScrollBar.setValue(contentScrollBar.maximum())

    def sendMessage(self):
        if self.userInputMultiline.isVisible():
            self.multilineButtonClicked()
        self.getResponse()

    def getResponse(self):
        if self.progressBar.isVisible() and config.chatGPTApiNoOfChoices == 1:
            stop_file = ".stop_chatgpt"
            if not os.path.isfile(stop_file):
                open(stop_file, "a", encoding="utf-8").close()
        elif not self.progressBar.isVisible():
            userInput = self.userInput.text().strip()
            if userInput:
                self.userInput.setDisabled(True)
                if config.chatGPTApiNoOfChoices == 1:
                    self.sendButton.setText(config.thisTranslation["stop"])
                    self.busyLoading = True
                    self.listView.setDisabled(True)
                    self.newButton.setDisabled(True)
                messages = self.getMessages(userInput)
                self.print(f">>> {userInput}")
                self.saveData()
                self.currentLoadingID = self.contentID
                self.currentLoadingContent = self.contentView.toPlainText().strip()
                self.progressBar.show()
                ChatGPTResponse(self).workOnGetResponse(messages)

    def fileNamesWithoutExtension(self, dir, ext):
        files = glob.glob(os.path.join(dir, "*.{0}".format(ext)))
        return sorted(
            [
                file[len(dir) + 1 : -(len(ext) + 1)]
                for file in files
                if os.path.isfile(file)
            ]
        )

    def processResponse(self, responses):
        if responses:
            self.contentID = self.currentLoadingID
            self.contentView.setPlainText(self.currentLoadingContent)
            self.currentLoadingID = self.currentLoadingContent = ""
            self.print(responses)
            if config.chatGPTApiAutoScrolling:
                contentScrollBar = self.contentView.verticalScrollBar()
                contentScrollBar.setValue(contentScrollBar.maximum())
        self.userInput.setText("")
        self.saveData()
        self.userInput.setEnabled(True)
        if config.chatGPTApiNoOfChoices == 1:
            self.listView.setEnabled(True)
            self.newButton.setEnabled(True)
            self.busyLoading = False
        self.sendButton.setText(config.thisTranslation["send"])
        self.progressBar.hide()
        self.setUserInputFocus()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.chatGPT = QChatGpt(self)
        self.setCentralWidget(self.chatGPT)
        menubar = self.menuBar()
        file_menu = menubar.addMenu(config.thisTranslation["chat"])
        new_action = QAction(config.thisTranslation["openDatabase"], self)
        new_action.setShortcut("Ctrl+Shift+O")
        new_action.triggered.connect(self.chatGPT.openDatabase)
        file_menu.addAction(new_action)
        new_action = QAction(config.thisTranslation["newDatabase"], self)
        new_action.setShortcut("Ctrl+Shift+N")
        new_action.triggered.connect(self.chatGPT.newDatabase)
        file_menu.addAction(new_action)
        new_action = QAction(config.thisTranslation["saveDatabaseAs"], self)
        new_action.setShortcut("Ctrl+Shift+S")
        new_action.triggered.connect(
            lambda: self.chatGPT.newDatabase(copyExistingDatabase=True)
        )
        file_menu.addAction(new_action)
        file_menu.addSeparator()
        new_action = QAction(config.thisTranslation["fileManager"], self)
        new_action.setShortcut("Ctrl+O")
        new_action.triggered.connect(self.openDatabaseDirectory)
        file_menu.addAction(new_action)
        file_menu.addSeparator()
        new_action = QAction(config.thisTranslation["newChat"], self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.chatGPT.newData)
        file_menu.addAction(new_action)
        new_action = QAction(config.thisTranslation["saveChat"], self)
        new_action.setShortcut("Ctrl+S")
        new_action.triggered.connect(self.chatGPT.saveData)
        file_menu.addAction(new_action)
        new_action = QAction(config.thisTranslation["printChat"], self)
        new_action.setShortcut("Ctrl+P")
        new_action.triggered.connect(self.chatGPT.printData)
        file_menu.addAction(new_action)
        file_menu.addSeparator()
        file_menu.addSeparator()
        new_action = QAction(config.thisTranslation["toggleSystemTray"], self)
        new_action.triggered.connect(self.toggleSystemTray)
        file_menu.addAction(new_action)
        new_action = QAction(config.thisTranslation["toggleMultilineInput"], self)
        new_action.setShortcut("Ctrl+L")
        new_action.triggered.connect(self.chatGPT.multilineButtonClicked)
        file_menu.addAction(new_action)
        file_menu.addSeparator()
        exit_action = QAction(config.thisTranslation["exit"], self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip(config.thisTranslation["exitTheApplication"])
        exit_action.triggered.connect(QGuiApplication.instance().quit)
        file_menu.addAction(exit_action)
        self.resize(QGuiApplication.primaryScreen().availableSize() * 3 / 4)
        self.show()

    def openDatabaseDirectory(self):
        databaseDirectory = os.path.dirname(
            os.path.abspath(config.chatGPTApiLastChatDatabase)
        )
        thisOS = platform.system()
        if thisOS == "Windows":
            openCommand = "start"
        elif thisOS == "Darwin":
            openCommand = "open"
        elif thisOS == "Linux":
            openCommand = "xdg-open"
        os.system(f"{openCommand} {databaseDirectory}")

    def toggleSystemTray(self):
        config.enableSystemTray = not config.enableSystemTray
        QMessageBox.information(
            self,
            "ChatGPT-GUI",
            "You need to restart this application to make the changes effective.",
        )

    def isWayland(self):
        if (
            platform.system() == "Linux"
            and (not os.getenv("QT_QPA_PLATFORM") is None)
            and (os.getenv("QT_QPA_PLATFORM") == "wayland")
        ):
            return True
        else:
            return False

    def bringToForeground(self, window):
        if window and (not (window.isVisible() and window.isActiveWindow())):
            window.raise_()
            if window.isVisible() and (not window.isActiveWindow()):
                window.hide()
            window.show()
            if not self.isWayland():
                window.activateWindow()


if __name__ == "__main__":

    def showMainWindow():
        if not hasattr(config, "mainWindow") or config.mainWindow is None:
            config.mainWindow = MainWindow()
        else:
            config.mainWindow.bringToForeground(config.mainWindow)

    def aboutToQuit():
        with open("config.py", "w", encoding="utf-8") as fileObj:
            for name in dir(config):
                if not name.startswith("__") and (
                    not name
                    in (
                        "mainWindow",
                        "chatGPTApi",
                        "chatGPTTransformers",
                        "predefinedContext",
                        "predefinedContexts",
                        "inputSuggestions",
                    )
                ):
                    try:
                        value = eval(f"config.{name}")
                        fileObj.write("{0} = {1}\n".format(name, pprint.pformat(value)))
                    except:
                        pass

    thisOS = platform.system()
    appName = "ChatGPT-GUI"
    if thisOS == "Windows":
        myappid = "chatgpt.gui"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        windowsIconPath = os.path.abspath(
            os.path.join(sys.path[0], "icons", f"{appName}.ico")
        )
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(windowsIconPath)
    app = QApplication(sys.argv)
    iconPath = os.path.abspath(os.path.join(sys.path[0], "icons", f"{appName}.png"))
    app.setStyleSheet(qdarkstyle.load_stylesheet())
    appIcon = QIcon(iconPath)
    app.setWindowIcon(appIcon)
    showMainWindow()
    app.aboutToQuit.connect(aboutToQuit)
    if thisOS == "Windows":
        desktopPath = os.path.join(os.path.expanduser("~"), "Desktop")
        shortcutDir = desktopPath if os.path.isdir(desktopPath) else wd
        shortcutBat1 = os.path.join(shortcutDir, f"{appName}.bat")
        shortcutCommand1 = f'''powershell.exe -NoExit -Command "python '{this_file}'"'''
        if not os.path.exists(shortcutBat1):
            try:
                with open(shortcutBat1, "w") as fileObj:
                    fileObj.write(shortcutCommand1)
            except:
                pass
    elif thisOS == "Darwin":
        shortcut_file = os.path.expanduser(f"~/Desktop/{appName}.command")
        if not os.path.isfile(shortcut_file):
            with open(shortcut_file, "w") as f:
                f.write("#!/bin/bash\n")
                f.write(f"cd {wd}\n")
                f.write(f"{sys.executable} {this_file} gui\n")
            os.chmod(shortcut_file, 493)
    elif thisOS == "Linux":

        def desktopFileContent():
            iconPath = os.path.join(wd, "icons", "ChatGPT-GUI.png")
            return "#!/usr/bin/env xdg-open\n\n[Desktop Entry]\nVersion=1.0\nType=Application\nTerminal=false\nPath={0}\nExec={1} {2}\nIcon={3}\nName=ChatGPT GUI\n".format(
                wd, sys.executable, this_file, iconPath
            )

        ubaLinuxDesktopFile = os.path.join(wd, f"{appName}.desktop")
        if not os.path.exists(ubaLinuxDesktopFile):
            with open(ubaLinuxDesktopFile, "w") as fileObj:
                fileObj.write(desktopFileContent())
            try:
                from pathlib import Path

                userAppDir = os.path.join(
                    str(Path.home()), ".local", "share", "applications"
                )
                userAppDirShortcut = os.path.join(userAppDir, f"{appName}.desktop")
                if not os.path.exists(userAppDirShortcut):
                    Path(userAppDir).mkdir(parents=True, exist_ok=True)
                    copyfile(ubaLinuxDesktopFile, userAppDirShortcut)
                homeDir = os.environ["HOME"]
                desktopPath = f"{homeDir}/Desktop"
                desktopPathShortcut = os.path.join(desktopPath, f"{appName}.desktop")
                if os.path.isfile(desktopPath) and (
                    not os.path.isfile(desktopPathShortcut)
                ):
                    copyfile(ubaLinuxDesktopFile, desktopPathShortcut)
            except:
                pass
    if config.enableSystemTray:
        app.setQuitOnLastWindowClosed(False)
        tray = QSystemTrayIcon()
        tray.setIcon(appIcon)
        tray.setToolTip("ChatGPT-GUI")
        tray.setVisible(True)
        trayMenu = QMenu()
        showMainWindowAction = QAction(config.thisTranslation["show"])
        showMainWindowAction.triggered.connect(showMainWindow)
        trayMenu.addAction(showMainWindowAction)
        trayMenu.addSeparator()
        quitAppAction = QAction(config.thisTranslation["exit"])
        quitAppAction.triggered.connect(app.quit)
        trayMenu.addAction(quitAppAction)
        tray.setContextMenu(trayMenu)
    sys.exit(app.exec() if config.qtLibrary == "pyside6" else app.exec_())
