styleSheet = '''

QFrame#boundingBox {
     border: 2px solid black;
     border-radius: 4px;
     padding: 2px;
 }

QLabel#header
{
    font: bold;
    font-size: 22px;
    border: 2px solid #ffb900;
    border-radius: 4px;
    padding: 2px;
    margin: 2px;
}

QLabel
{
    font-size: 14px;
}

QPushButton {
    background-color: #ffb900;
    border-style: outset;
    border-width: 2px;
    border-radius: 10px;
    border-color: black;
    font: bold "Arial" 22px;
    min-width: 24em;
    min-height: 4em;
    padding: 8px;
}

QPushButton#abort {
    background-color: #ff3900;
    border-style: outset;
    border-width: 2px;
    border-radius: 10px;
    border-color: black;
    font: bold "Arial" 14px;
    color: white;
    min-width: 10em;
    min-height: 4em;
    padding: 8px;
}

QPushButton:pressed#abort {
    background-color: #bf2c02;
    border-style: outset;
    border-width: 2px;
    border-radius: 10px;
    border-color: black;
    font: bold "Arial" 14px;
    color: white;
    min-width: 10em;
    min-height: 4em;
    padding: 8px;
}

QPushButton:pressed {
    background-color: #826007;
    border-style: outset;
    border-width: 2px;
    border-radius: 10px;
    border-color: black;
    font: bold "Arial" 14px;
    min-width: 10em;
    min-height: 4em;
    padding: 8px;
}



QPushButton:disabled {
    background-color: #F6D98E;
    border-style: outset;
    border-width: 2px;
    border-radius: 10px;
    border-color: red;
    font: bold "Arial" 14px;
    min-width: 10em;
    min-height: 5em;
    padding: 8px;
}

QPushButton#rackButton {
    background-color: #ffb900;
    border-style: outset;
    border-width: 2px;
    border-radius: 10px;
    border-color: black;
    font: bold "Arial" 22px;
    min-width: 14em;
    min-height: 4em;
    padding: 8px;
}

QPushButton:checked#rackButton {
    background-color: #00D100;
    border-style: outset;
    border-width: 2px;
    border-radius: 10px;
    border-color: black;
    font: bold "Arial" 14px;
    min-width: 14em;
    min-height: 4em;
    padding: 8px;
}

QTabWidget::pane { /* The tab widget frame */
    border-top: 2px solid #C2C7CB;
}

QTabWidget::tab-bar {
    left: 5px; /* move to the right by 5px */
}

/* Style the tab using the tab sub-control. Note that
    it reads QTabBar _not_ QTabWidget */
QTabBar::tab {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                stop: 0 #E1E1E1, stop: 0.4 #DDDDDD,
                                stop: 0.5 #D8D8D8, stop: 1.0 #D3D3D3);
    border: 2px solid #C4C4C3;
    border-bottom-color: #C2C7CB; /* same as the pane color */
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    min-width: 20em;
    min-height:2em;
    padding: 2px;
}

QTabBar::tab:selected, QTabBar::tab:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                stop: 0 #fafafa, stop: 0.4 #f4f4f4,
                                stop: 0.5 #e7e7e7, stop: 1.0 #fafafa);
}

QTabBar::tab:selected {
    border-color: #9B9B9B;
    border-bottom-color: #C2C7CB; /* same as pane color */
}

QTabBar::tab:!selected {
    margin-top: 2px; /* make non-selected tabs look smaller */
}

QComboBox {
    border: 1px solid gray;
    border-radius: 3px;
    padding: 1px 18px 1px 3px;
    min-width: 6em;
    font-size: 14px;
}

QComboBox:editable {
    background: white;
}

QComboBox:on { 
    padding-top: 3px;
    padding-left: 4px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 15px;

    border-left-width: 1px;
    border-left-color: darkgray;
    border-left-style: solid;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
}

QTabWidget#main {
    font: bold "Arial" 32px;
}

QComboBox::down-arrow:on { 
    top: 2px;
    left: 2px;
}

QComboBox QAbstractItemView::item:!enabled
{
    color:red;
}


QLineEdit {
    min-width: 150px;
    max-width: 250px;
    font-size: 14px;
}

QLineEdit[readOnly="true"] { 
    min-width: 200px;
    max-width: 300px;
    border: 2px solid grey;
    border-radius: 2px;
    background-color:  #ffb900;
    font-size: 14px;
}

QProgressBar {
    border: 2px solid grey;
    border-radius: 5px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #2141a3;
    width: 20px;
}

QProgressBar::chunk[status="testing"] {
    background-color: #2141a3;
    width: 20px;
}

QProgressBar::chunk[status="complete"] {
    background-color: #41a321;
    width: 20px;
}

QProgressBar::chunk[status="abort"] {
    background-color: #ff3900;
    width: 20px;
}

QFrame#logger {
    min-width:100em;
    min-height:100em;
}

QTextEdit {
    min-width:100em;
    min-height:50em;
}
'''