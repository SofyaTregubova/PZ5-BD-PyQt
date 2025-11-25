import os
import sys


os.environ[
    'QT_QPA_PLATFORM_PLUGIN_PATH'] = r'C:\Users\Софья\AppData\Roaming\Python\Python39\site-packages\PyQt5\Qt5\plugins'

# ДАЛЕЕ ВЕСЬ ТВОЙ ИСХОДНЫЙ КОД БЕЗ ИЗМЕНЕНИЙ
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox,
                             QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
                             QTabWidget, QProgressBar, QGroupBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor

BASE = "https://world.openfoodfacts.org"
HEADERS = {
    "User-Agent": "Darcons-Trade-CalorieFetcher/1.0 (+https://darcons-trade.example)"
}


def get_product_by_barcode(barcode: str, fields=None, lang="ru", country="ru") -> dict:
    if fields is None:
        fields = "code,product_name,nutriments,brands,quantity,serving_size,language,lang,lc"
    url = f"{BASE}/api/v2/product/{barcode}"
    params = {"fields": fields, "lc": lang, "cc": country}
    r = requests.get(url, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def search_products(query: str, page_size=5, fields=None, lang="ru", country="ru") -> dict:
    if fields is None:
        fields = "code,product_name,brands,nutriments,quantity,serving_size,ecoscore_grade"
    url = f"{BASE}/api/v2/search"
    params = {
        "search_terms": query,
        "fields": fields,
        "page_size": page_size,
        "lc": lang,
        "cc": country,
    }
    r = requests.get(url, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def extract_kcal(nutriments: dict) -> dict:
    get = nutriments.get
    data = {
        "kcal_100g": get("energy-kcal_100g") or get("energy-kcal_value"),
        "protein_100g": get("proteins_100g"),
        "fat_100g": get("fat_100g"),
        "carbs_100g": get("carbohydrates_100g"),
        "kcal_serving": get("energy-kcal_serving"),
        "protein_serving": get("proteins_serving"),
        "fat_serving": get("fat_serving"),
        "carbs_serving": get("carbohydrates_serving"),
    }
    return {k: v for k, v in data.items() if v is not None}


class ApiWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, search_type, query):
        super().__init__()
        self.search_type = search_type
        self.query = query

    def run(self):
        try:
            if self.search_type == 'barcode':
                result = get_product_by_barcode(self.query)
                if result.get("product"):
                    result = {"products": [result["product"]]}
                else:
                    result = {"products": []}
            else:
                result = search_products(self.query, page_size=10)

            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class NutritionApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Анализатор калорийности продуктов")
        self.setGeometry(100, 100, 900, 700)
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        title = QLabel("🍎 Анализатор калорийности продуктов")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #2E8B57; margin: 10px;")
        layout.addWidget(title)

        tabs = QTabWidget()

        search_tab = self.create_search_tab()
        tabs.addTab(search_tab, "🔍 Поиск продуктов")

        self.results_tab = self.create_results_tab()
        tabs.addTab(self.results_tab, "📊 Результаты")

        layout.addWidget(tabs)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def create_search_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        barcode_group = QGroupBox("Поиск по штрихкоду")
        barcode_layout = QVBoxLayout(barcode_group)

        barcode_input_layout = QHBoxLayout()
        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Введите штрихкод продукта...")
        self.barcode_input.returnPressed.connect(self.search_by_barcode)
        barcode_input_layout.addWidget(self.barcode_input)

        barcode_btn = QPushButton("Найти")
        barcode_btn.clicked.connect(self.search_by_barcode)
        barcode_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        barcode_input_layout.addWidget(barcode_btn)

        barcode_layout.addLayout(barcode_input_layout)
        layout.addWidget(barcode_group)

        text_group = QGroupBox("Поиск по названию")
        text_layout = QVBoxLayout(text_group)

        text_input_layout = QHBoxLayout()
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Введите название продукта...")
        self.text_input.returnPressed.connect(self.search_by_text)
        text_input_layout.addWidget(self.text_input)

        text_btn = QPushButton("Найти")
        text_btn.clicked.connect(self.search_by_text)
        text_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; }")
        text_input_layout.addWidget(text_btn)

        text_layout.addLayout(text_input_layout)
        layout.addWidget(text_group)

        examples_group = QGroupBox("Примеры для тестирования")
        examples_layout = QVBoxLayout(examples_group)
        examples_text = QLabel("5449000000996 - Coca-Cola\n3017620422003 - Nutella\n7613034626844 - Nesquik")
        examples_text.setStyleSheet("color: #666; font-size: 11px;")
        examples_layout.addWidget(examples_text)
        layout.addWidget(examples_group)

        layout.addStretch()
        return widget

    def create_results_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(8)
        self.results_table.setHorizontalHeaderLabels([
            "Штрихкод", "Название", "Бренд", "Калории/100г",
            "Белки/100г", "Жиры/100г", "Углеводы/100г", "Размер порции"
        ])

        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.results_table)

        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(150)
        self.details_text.setPlaceholderText("Выберите продукт для просмотра детальной информации...")
        layout.addWidget(self.details_text)

        self.results_table.itemSelectionChanged.connect(self.show_product_details)
        return widget

    def search_by_barcode(self):
        barcode = self.barcode_input.text().strip()
        if not barcode:
            QMessageBox.warning(self, "Ошибка", "Введите штрихкод")
            return
        self.start_search('barcode', barcode)

    def search_by_text(self):
        query = self.text_input.text().strip()
        if not query:
            QMessageBox.warning(self, "Ошибка", "Введите название продукта")
            return
        self.start_search('text', query)

    def start_search(self, search_type, query):
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        self.barcode_input.setEnabled(False)
        self.text_input.setEnabled(False)

        self.worker = ApiWorker(search_type, query)
        self.worker.finished.connect(self.handle_search_results)
        self.worker.error.connect(self.handle_search_error)
        self.worker.start()

    def handle_search_results(self, result):
        self.progress_bar.setVisible(False)
        self.barcode_input.setEnabled(True)
        self.text_input.setEnabled(True)

        products = result.get("products", [])
        if not products:
            QMessageBox.information(self, "Результат", "Продукты не найдены")
            return
        self.display_results(products)

    def handle_search_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.barcode_input.setEnabled(True)
        self.text_input.setEnabled(True)
        QMessageBox.critical(self, "Ошибка", f"Ошибка при поиске: {error_msg}")

    def display_results(self, products):
        self.results_table.setRowCount(len(products))

        for row, product in enumerate(products):
            self.results_table.setItem(row, 0, QTableWidgetItem(product.get("code", "")))
            self.results_table.setItem(row, 1, QTableWidgetItem(product.get("product_name", "Неизвестно")))
            self.results_table.setItem(row, 2, QTableWidgetItem(product.get("brands", "")))

            nutriments = extract_kcal(product.get("nutriments", {}))
            self.results_table.setItem(row, 3, QTableWidgetItem(str(nutriments.get("kcal_100g", "Н/Д"))))
            self.results_table.setItem(row, 4, QTableWidgetItem(str(nutriments.get("protein_100g", "Н/Д"))))
            self.results_table.setItem(row, 5, QTableWidgetItem(str(nutriments.get("fat_100g", "Н/Д"))))
            self.results_table.setItem(row, 6, QTableWidgetItem(str(nutriments.get("carbs_100g", "Н/Д"))))
            self.results_table.setItem(row, 7, QTableWidgetItem(product.get("quantity", "Н/Д")))

    def show_product_details(self):
        current_row = self.results_table.currentRow()
        if current_row == -1:
            return

        product_name = self.results_table.item(current_row, 1).text()
        barcode = self.results_table.item(current_row, 0).text()
        brand = self.results_table.item(current_row, 2).text()

        try:
            result = get_product_by_barcode(barcode)
            if result.get("product"):
                product = result["product"]
                nutriments = extract_kcal(product.get("nutriments", {}))

                details = f"""
📦 <b>Детальная информация о продукте:</b>

🏷️ <b>Название:</b> {product_name}
🏭 <b>Бренд:</b> {brand}
📋 <b>Штрихкод:</b> {barcode}
📏 <b>Количество:</b> {product.get('quantity', 'Н/Д')}
🍽️ <b>Размер порции:</b> {product.get('serving_size', 'Н/Д')}

⚖️ <b>Пищевая ценность на 100г:</b>
• Калории: {nutriments.get('kcal_100g', 'Н/Д')} ккал
• Белки: {nutriments.get('protein_100g', 'Н/Д')} г
• Жиры: {nutriments.get('fat_100g', 'Н/Д')} г  
• Углеводы: {nutriments.get('carbs_100g', 'Н/Д')} г
                """
                self.details_text.setHtml(details)
        except Exception as e:
            self.details_text.setText(f"Ошибка при загрузке деталей: {str(e)}")


def main():
    app = QApplication(sys.argv)
    window = NutritionApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()