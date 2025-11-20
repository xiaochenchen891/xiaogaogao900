# app.py
import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import urllib.parse
import os
import tempfile
import warnings
from scipy import stats
import logging
import shutil
import io
import re
import calendar
from dateutil.relativedelta import relativedelta
warnings.filterwarnings('ignore')

# 设置 logging 配置
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# ====================== 页面配置 ======================
st.set_page_config(
    page_title="同花顺问财监控系统",
    page_icon="📈",
    layout="wide"
)
st.title("同花监控系统")
st.markdown("---")

# ====================== StockMonitor 类 ======================
class StockMonitor:
    def __init__(self):
        self.driver = None
        self.download_dir = tempfile.mkdtemp()
        self.profile_dir = tempfile.mkdtemp()
        # 固化匹配缓存
        self.cached_selectors = {
            'search_box': {
                'selector': "//textarea[contains(@placeholder,'请输入')]",
                'description': "搜索框 - 请输入概念、价升量缩等，多个条",
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            'search_button': {
                'selector': "//*[contains(@class,'search-icon')]",
                'description': "搜索按钮 - 无文本",
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            'download_button': None
        }
        # 监控数据存储
        self.monitoring_data = {
            'timestamps': [],
            'stock_counts': [],
            'stock_lists': [],
            'slope_data': [],
            'closing_sequences': [],
            'date_columns': [],
            'stock_names': [],
            'new_stocks': []
        }
        # 监控状态
        self.is_monitoring = False
        self.last_execution_time = None
        self.next_execution_time = None
        self.monitoring_interval = 5
        self.cycle_count = 1
        # 延迟初始化浏览器
        self.driver_initialized = False
        # 登录状态
        self.is_logged_in = False
        self.login_attempted = False
        # 下载历史
        self.last_download_time = None
        self.downloaded_files_history = []
        # 倒计时
        self.countdown_seconds = 0

    # ==================== 使用 webdriver-manager 自动管理浏览器驱动 ====================
    def initialize_driver(self):
        if self.driver_initialized and self.driver:
            logging.debug("步骤: Driver already initialized.")
            return True
        
        try:
            return self.initialize_chrome_with_manager()
        except Exception as e:
            logging.error(f"Chrome initialization failed: {str(e)}")
            try:
                return self.initialize_edge_with_manager()
            except Exception as e2:
                logging.error(f"Edge initialization also failed: {str(e2)}")
                st.error(f"所有浏览器初始化失败。错误: {str(e)}")
                return False

    def initialize_chrome_with_manager(self):
        """使用 webdriver-manager 自动管理 Chrome 驱动"""
        try:
            logging.debug("步骤: Initializing Chrome with webdriver-manager...")
            
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.chrome.service import Service as ChromeService
            from webdriver_manager.chrome import ChromeDriverManager
            
            chrome_options = ChromeOptions()
            
            # 基本配置
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 用户数据目录配置
            if self.profile_dir:
                chrome_options.add_argument(f'--user-data-dir={self.profile_dir}')
            
            # 性能优化参数
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            
            # 下载配置
            prefs = {
                "download.default_directory": self.download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": False,
                "profile.default_content_settings.popups": 0,
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # 使用 webdriver-manager 自动下载和管理 ChromeDriver
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            self.driver.maximize_window()
            self.driver.implicitly_wait(5)
            self.driver_initialized = True
            logging.debug("步骤: Chrome driver initialized successfully with webdriver-manager.")
            st.success("✅ 已成功使用 Chrome 浏览器")
            return True
            
        except Exception as e:
            logging.error(f"Error initializing Chrome with webdriver-manager: {str(e)}")
            raise e

    def initialize_edge_with_manager(self):
        """使用 webdriver-manager 自动管理 Edge 驱动"""
        try:
            logging.debug("步骤: Initializing Edge with webdriver-manager...")
            
            from selenium.webdriver.edge.options import Options as EdgeOptions
            from selenium.webdriver.edge.service import Service as EdgeService
            from webdriver_manager.microsoft import EdgeChromiumDriverManager
            
            edge_options = EdgeOptions()
            
            # 基本配置
            edge_options.add_argument('--no-sandbox')
            edge_options.add_argument('--disable-dev-shm-usage')
            edge_options.add_argument('--disable-blink-features=AutomationControlled')
            edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            edge_options.add_experimental_option('useAutomationExtension', False)
            
            # 用户数据目录配置
            if self.profile_dir:
                edge_options.add_argument(f'--user-data-dir={self.profile_dir}')
            
            # 性能优化参数
            edge_options.add_argument('--disable-gpu')
            edge_options.add_argument('--disable-extensions')
            edge_options.add_argument('--disable-plugins')
            
            # 下载配置
            prefs = {
                "download.default_directory": self.download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": False,
                "profile.default_content_settings.popups": 0,
            }
            edge_options.add_experimental_option("prefs", prefs)
            
            # 使用 webdriver-manager 自动下载和管理 EdgeDriver
            service = EdgeService(EdgeChromiumDriverManager().install())
            self.driver = webdriver.Edge(service=service, options=edge_options)
            
            self.driver.maximize_window()
            self.driver.implicitly_wait(5)
            self.driver_initialized = True
            logging.debug("步骤: Edge driver initialized successfully with webdriver-manager.")
            st.success("✅ 已成功使用 Edge 浏览器")
            return True
            
        except Exception as e:
            logging.error(f"Error initializing Edge with webdriver-manager: {str(e)}")
            raise e

    # ==================== 简化的导航方法 ====================
    def ensure_navigation(self, force_refresh=False):
        if not self.initialize_driver():
            logging.error("步骤: Failed to initialize driver for navigation.")
            st.error("❌ 浏览器初始化失败，请检查控制台输出")
            return False
        
        try:
            logging.debug("步骤: Ensuring navigation...")
            target_url = "https://www.iwencai.com/unifiedwap/"
            
            if force_refresh:
                logging.debug(f"步骤: Force refreshing to {target_url}")
                self.driver.get(target_url)
            else:
                current_url = self.driver.current_url
                if target_url not in current_url:
                    logging.debug(f"步骤: Navigating to {target_url}")
                    self.driver.get(target_url)
            
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            logging.debug("步骤: Navigation successful.")
            return True
            
        except Exception as e:
            logging.error(f"Error in navigation: {str(e)}")
            st.error(f"❌ 导航失败: {str(e)}")
            return False

    # ==================== 简化的登录处理 ====================
    def handle_login_smartly(self):
        """简化的登录处理"""
        try:
            logging.debug("步骤: Checking for login requirement...")
            
            login_indicators = [
                "//div[contains(text(), '扫码登录')]",
                "//div[contains(@class, 'login')]",
                "//div[contains(@class, 'qrcode')]",
            ]
            
            for selector in login_indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        if element.is_displayed():
                            logging.debug(f"步骤: Login popup detected with: {selector}")
                            return self.wait_for_login_completion()
                except:
                    continue
            
            logging.debug("步骤: No login required.")
            return True
            
        except Exception as e:
            logging.error(f"Error in login handling: {str(e)}")
            return False

    def wait_for_login_completion(self, timeout=120):
        """等待登录完成"""
        logging.debug("步骤: Waiting for login completion...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            login_visible = False
            try:
                login_elements = self.driver.find_elements(By.XPATH, "//div[contains(text(), '扫码登录')]")
                for element in login_elements:
                    if element.is_displayed():
                        login_visible = True
                        break
            except:
                pass
            
            if not login_visible:
                self.is_logged_in = True
                logging.debug("步骤: Login completed successfully.")
                time.sleep(2)
                return True
            
            time.sleep(2)
        
        logging.warning("步骤: Login timeout.")
        return False

    # ==================== 改进的下载流程 ====================
    def smart_download_flow_optimized(self):
        """改进的下载流程"""
        try:
            logging.debug("步骤: Starting optimized download flow...")
            
            download_start_time = time.time()
            
            self.clean_download_directory()
            
            btn = self.find_and_cache_download_button()
            if not btn:
                logging.error("步骤: Download button not found.")
                btn = self.find_alternative_download_button()
                if not btn:
                    return False
            
            logging.debug("步骤: Clicking download button...")
            try:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", btn)
            except Exception as e:
                logging.error(f"JavaScript click failed: {str(e)}")
                try:
                    btn.click()
                except Exception as e2:
                    logging.error(f"Regular click also failed: {str(e2)}")
                    return False
            
            time.sleep(3)
            if not self.is_logged_in:
                self.handle_login_smartly()
            
            if self.is_logged_in:
                time.sleep(3)
                btn = self.find_and_cache_download_button()
                if btn:
                    try:
                        self.driver.execute_script("arguments[0].click();", btn)
                    except:
                        btn.click()
            
            return self.wait_for_download_complete_fast(download_start_time, timeout=60)
            
        except Exception as e:
            logging.error(f"Error in download flow: {str(e)}")
            return False

    def clean_download_directory(self):
        """清空下载目录"""
        try:
            files = os.listdir(self.download_dir)
            for file in files:
                file_path = os.path.join(self.download_dir, file)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        logging.debug(f"步骤: Removed old file: {file}")
                except Exception as e:
                    logging.warning(f"Could not remove file {file}: {str(e)}")
        except Exception as e:
            logging.error(f"Error cleaning download directory: {str(e)}")

    def find_alternative_download_button(self):
        """尝试其他下载按钮选择器"""
        alternative_selectors = [
            "//*[contains(@class, 'download')]",
            "//*[contains(text(), '导出')]",
            "//*[contains(text(), '下载')]",
            "//button[contains(@class, 'btn-download')]",
            "//a[contains(@class, 'download')]",
            "//span[contains(text(), '导出')]",
            "//span[contains(text(), '下载')]",
        ]
        
        for sel in alternative_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, sel)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        text = element.text or '无文本'
                        logging.debug(f"步骤: Alternative download button found: {sel} - {text}")
                        return element
            except:
                continue
        
        logging.warning("步骤: No alternative download button found.")
        return None

    def wait_for_download_complete_fast(self, start_time, timeout=60):
        """改进的下载等待方法，基于时间戳检测新文件"""
        try:
            logging.debug("步骤: Waiting for download...")
            temp_extensions = ['.crdownload', '.part', '.tmp', '.temp']
            
            wait_start_time = time.time()
            
            while time.time() - wait_start_time < timeout:
                try:
                    files = os.listdir(self.download_dir)
                    logging.debug(f"步骤: Current files in directory: {files}")
                    
                    for file in files:
                        file_path = os.path.join(self.download_dir, file)
                        
                        if any(file.endswith(ext) for ext in temp_extensions):
                            logging.debug(f"步骤: Skipping temp file: {file}")
                            continue
                            
                        if os.path.getsize(file_path) > 0:
                            mtime = os.path.getmtime(file_path)
                            ctime = os.path.getctime(file_path)
                            file_time = max(mtime, ctime)
                            
                            if file_time >= start_time:
                                logging.debug(f"步骤: Download completed with file: {file}")
                                logging.debug(f"步骤: File time: {file_time}, Start time: {start_time}")
                                return True
                            
                            file_size = os.path.getsize(file_path)
                            logging.debug(f"步骤: File {file} - Size: {file_size}, Time: {file_time}")
                except Exception as e:
                    logging.error(f"Error checking download directory: {str(e)}")
                
                time.sleep(2)
            
            files = os.listdir(self.download_dir)
            if files:
                logging.warning(f"步骤: Timeout but found files: {files}")
                for file in files:
                    file_path = os.path.join(self.download_dir, file)
                    if os.path.getsize(file_path) > 0:
                        logging.warning(f"步骤: Using existing file: {file}")
                        return True
                
            logging.warning("步骤: Download timeout.")
            return False
            
        except Exception as e:
            logging.error(f"Error waiting for download: {str(e)}")
            return False

    def find_and_cache_download_button(self):
        logging.debug("步骤: Searching for download button...")
        selectors = [
            "//div[contains(@class, 'item')]//div[contains(@class, 'download')]/../div[contains(@class, 'text') and text()='导数据']",
            "//div[contains(@class, 'text') and text()='导数据']",
            "//div[contains(@class, 'item')]//div[contains(@class, 'download')]",
            "//button[contains(text(), '导数据')]",
            "//span[contains(text(), '导数据')]",
            "//a[contains(text(), '导数据')]",
            "//div[contains(text(), '导数据')]",
        ]
        for sel in selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, sel)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        text = element.text or '无文本'
                        self.save_selector_to_cache('download_button', sel, f"下载按钮 - {text}")
                        logging.debug(f"步骤: Download button found: {sel}")
                        return element
            except:
                continue
        logging.warning("步骤: No download button found.")
        return None

    def save_selector_to_cache(self, element_type, selector, description=""):
        self.cached_selectors[element_type] = {
            'selector': selector,
            'description': description,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    # ==================== 一键自动化 ====================
    def one_click_automation_with_refresh(self, search_query):
        try:
            logging.debug("步骤: Starting automation...")
            
            if not self.ensure_navigation(force_refresh=True):
                return False
            time.sleep(3)
            
            if not self.find_search_box_with_cache(search_query):
                return False
            
            if not self.find_search_button_with_cache():
                return False
            time.sleep(5)
            
            if not self.smart_download_flow_optimized():
                return False
            
            logging.debug("步骤: Automation completed successfully.")
            return True
            
        except Exception as e:
            logging.error(f"Error in automation: {str(e)}")
            return False

    def find_search_box_with_cache(self, search_query):
        try:
            logging.debug(f"步骤: Filling search box: {search_query}")
            sel = self.cached_selectors['search_box']['selector']
            el = self.driver.find_element(By.XPATH, sel)
            if el.is_displayed() and el.is_enabled():
                el.click()
                time.sleep(0.5)
                el.clear()
                time.sleep(0.5)
                el.send_keys(search_query)
                logging.debug("步骤: Search box filled.")
                return True
        except Exception as e:
            logging.error(f"Error with search box: {str(e)}")
        return False

    def find_search_button_with_cache(self):
        try:
            logging.debug("步骤: Clicking search button...")
            sel = self.cached_selectors['search_button']['selector']
            el = self.driver.find_element(By.XPATH, sel)
            if el.is_displayed() and el.is_enabled():
                el.click()
                time.sleep(3)
                logging.debug("步骤: Search button clicked.")
                return True
        except Exception as e:
            logging.error(f"Error with search button: {str(e)}")
        return False

    # ==================== 专门优化的双表头处理方法 ====================
    def process_downloaded_data(self):
        try:
            logging.debug("步骤: Processing downloaded data...")
            files = os.listdir(self.download_dir)
            logging.debug(f"步骤: All files in download directory: {files}")
            
            if not files:
                logging.warning("步骤: No files in download directory.")
                return None
            
            latest_file = None
            latest_time = 0
            
            for file in files:
                file_path = os.path.join(self.download_dir, file)
                file_time = os.path.getmtime(file_path)
                if file_time > latest_time:
                    latest_time = file_time
                    latest_file = file
            
            if not latest_file:
                logging.warning("步骤: Could not determine latest file.")
                return None
                
            file_path = os.path.join(self.download_dir, latest_file)
            logging.debug(f"步骤: Processing latest file: {latest_file}")
            
            if latest_file.endswith('.csv'):
                df = self.read_iwencai_csv_improved(file_path)
            elif latest_file.endswith(('.xls', '.xlsx')):
                df = self.read_iwencai_excel_improved(file_path)
            else:
                df = self.auto_detect_iwencai_file_improved(file_path)
                
            if df is None or df.empty:
                logging.warning("步骤: Dataframe is empty or could not be read.")
                return None
                
            stock_count = len(df)
            slope_data, closing_sequences, date_columns, stock_names = self.calculate_slopes_improved(df)
            
            # 计算新出现的股票
            new_stocks = self.calculate_new_stocks(df)
            
            logging.debug(f"步骤: Successfully processed {stock_count} stocks")
            logging.debug(f"步骤: New stocks detected: {len(new_stocks)}")
            
            return {
                'timestamp': datetime.now(),
                'stock_count': stock_count,
                'stock_list': df,
                'slopes': slope_data,
                'closing_sequences': closing_sequences,
                'date_columns': date_columns,
                'stock_names': stock_names,
                'new_stocks': new_stocks
            }
        except Exception as e:
            logging.error(f"Error processing data: {str(e)}")
            return None

    def calculate_new_stocks(self, current_df):
        """计算新出现的股票"""
        new_stocks = []
        
        # 如果没有历史数据，所有股票都是新的
        if not self.monitoring_data['stock_lists']:
            for index, row in current_df.iterrows():
                stock_code = self.get_stock_code(row, current_df.columns)
                stock_name = self.get_stock_name(row, current_df.columns)
                new_stocks.append(f"{stock_code} {stock_name}".strip())
            return new_stocks
        
        # 获取上一次的股票列表
        last_df = self.monitoring_data['stock_lists'][-1]
        
        # 获取当前和上一次的股票代码集合
        current_stocks = set()
        for index, row in current_df.iterrows():
            stock_code = self.get_stock_code(row, current_df.columns)
            stock_name = self.get_stock_name(row, current_df.columns)
            current_stocks.add(f"{stock_code} {stock_name}".strip())
        
        last_stocks = set()
        for index, row in last_df.iterrows():
            stock_code = self.get_stock_code(row, last_df.columns)
            stock_name = self.get_stock_name(row, last_df.columns)
            last_stocks.add(f"{stock_code} {stock_name}".strip())
        
        # 计算新出现的股票
        new_stocks = list(current_stocks - last_stocks)
        
        return new_stocks

    def read_iwencai_excel_improved(self, file_path):
        """专门优化双表头处理的Excel读取方法 - 参考上传文件处理代码"""
        try:
            # 先读取前几行来检测表头结构
            df_raw = pd.read_excel(file_path, header=None, nrows=10)
            logging.debug("步骤: Raw Excel data preview:")
            for i in range(min(10, len(df_raw))):
                logging.debug(f"Row {i}: {df_raw.iloc[i].tolist()}")
            
            # 检测表头行数
            header_rows = self.detect_header_rows_improved(df_raw)
            logging.debug(f"步骤: Detected header rows: {header_rows}")
            
            if header_rows == 1:
                # 单表头情况
                df = pd.read_excel(file_path, header=0)
                df.columns = [str(c).strip() for c in df.columns]
            else:
                # 多行表头情况 - 使用上传文件处理代码的方法
                df = self.process_double_header_excel_improved(file_path, header_rows)
            
            df = self.basic_data_cleaning(df)
            
            logging.debug(f"步骤: Final columns after processing: {list(df.columns)}")
            return df
            
        except Exception as e:
            logging.error(f"Error reading improved Excel: {str(e)}")
            return pd.read_excel(file_path)

    def detect_header_rows_improved(self, df_preview):
        """改进的表头行数检测 - 参考上传文件处理代码"""
        header_keywords = ['代码', '名称', '收盘价', '开盘价', '5日均线', '均线', '财务诊断评分', 'undefined']
        
        for i in range(min(5, len(df_preview))):
            row_text = ' '.join([str(x) for x in df_preview.iloc[i] if pd.notna(x)])
            if any(keyword in row_text for keyword in header_keywords):
                if i == 0:
                    # 检查下一行是否包含日期或技术指标
                    if len(df_preview) > 1:
                        next_row_text = ' '.join([str(x) for x in df_preview.iloc[1] if pd.notna(x)])
                        if self.contains_date_or_technical_improved(next_row_text):
                            return 2
                    return 1
                else:
                    return i + 1
        
        return 1

    def contains_date_or_technical_improved(self, text):
        """检查文本是否包含日期或技术指标信息 - 改进版本"""
        date_indicators = ['2024', '2025', '收盘价', '开盘价', '均线', 'MA', 'undefined', '前', '后']
        text_str = str(text).lower()
        return any(indicator in text_str for indicator in date_indicators)

    def process_double_header_excel_improved(self, file_path, header_rows):
        """处理双表头 - 参考上传文件处理代码的方法"""
        try:
            # 读取原始数据
            df_raw = pd.read_excel(file_path, header=None)
            
            # 处理表头行，向前填充空值
            header_df = df_raw.iloc[:header_rows].ffill(axis=1)
            df = df_raw.iloc[header_rows:].reset_index(drop=True)
            
            # 构建合并列名 - 参考上传文件处理代码
            columns = []
            current_prefix = ""
            
            for col in header_df.values.T:
                col_strs = [str(x).strip() for x in col if str(x) != "nan"]
                if len(col_strs) == 0:
                    columns.append("")
                    continue
                    
                # 识别列类型前缀
                if "收盘价" in col_strs[0]:
                    current_prefix = "收盘价"
                elif "5日均线" in col_strs[0] or "均线" in col_strs[0]:
                    current_prefix = "5日均线"
                elif "开盘价" in col_strs[0]:
                    current_prefix = "开盘价"
                elif "财务诊断评分" in col_strs[0]:
                    current_prefix = "财务诊断评分"
                
                # 提取日期部分
                date_part = col_strs[-1] if len(col_strs) > 1 else col_strs[0]
                
                # 构建列名
                if current_prefix and "undefined" in col_strs[0]:
                    merged = f"{current_prefix}_{date_part}"
                else:
                    merged = "_".join(col_strs).strip("_")
                
                columns.append(merged)
            
            df.columns = columns
            return df
            
        except Exception as e:
            logging.error(f"Error processing double header improved: {str(e)}")
            return pd.read_excel(file_path, header=1)

    def basic_data_cleaning(self, df):
        """基础数据清洗"""
        if df is None or df.empty:
            return df
        
        df_clean = df.copy()
        
        for col in df_clean.select_dtypes(include=['object']).columns:
            try:
                df_clean[col] = df_clean[col].astype(str).str.strip().replace({
                    'nan': np.nan, 'None': np.nan, '': np.nan
                })
            except Exception:
                pass
        
        replace_symbols = ["-", "—", "空值", "null", "None", "", "NaN", "--"]
        df_clean.replace(replace_symbols, np.nan, inplace=True)
        
        for col in df_clean.columns:
            if df_clean[col].dtype == object:
                try:
                    df_clean[col] = df_clean[col].astype(str).str.replace(',', '').str.replace(' ', '')
                except Exception:
                    pass
                try:
                    df_clean[col] = pd.to_numeric(df_clean[col], errors='ignore')
                except Exception:
                    pass
        
        df_clean = df_clean.dropna(how='all')
        df_clean = df_clean.dropna(axis=1, how='all')
        
        df_clean = self.identify_stock_columns(df_clean)
        
        return df_clean

    def find_closing_price_columns(self, df):
        """查找收盘价列 - 改进版本，区分收盘价、开盘价和5日均线"""
        close_cols = []
        date_info = []
        
        for col in df.columns:
            col_str = str(col)
            
            # 只识别明确标记为收盘价的列
            is_closing_col = False
            if col_str.startswith('收盘价_'):
                is_closing_col = True
            elif '收盘价' in col_str and '开盘价' not in col_str and '5日均线' not in col_str:
                is_closing_col = True
            
            if is_closing_col:
                # 从列名中提取日期
                parts = str(col).split('_')
                if len(parts) > 1:
                    date_str_raw = parts[-1]
                    date_str = date_str_raw.split(' [')[0].strip()
                    
                    # 尝试多种日期格式解析
                    date_obj = None
                    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
                        try:
                            date_obj = datetime.strptime(date_str, fmt)
                            break
                        except:
                            continue
                    
                    if date_obj:
                        extracted_date = date_obj.strftime("%Y-%m-%d")
                    else:
                        # 如果无法解析，使用原始字符串
                        extracted_date = date_str
                else:
                    extracted_date = col_str
                
                if self.is_valid_price_column(df[col]):
                    close_cols.append(col)
                    date_info.append(extracted_date)
        
        logging.debug(f"步骤: Closing price columns found: {close_cols}")
        logging.debug(f"步骤: Corresponding dates: {date_info}")
        
        if close_cols and date_info:
            close_cols, date_info = self.sort_columns_by_date(close_cols, date_info)
            logging.debug(f"步骤: Sorted closing price columns: {close_cols}")
            logging.debug(f"步骤: Sorted dates: {date_info}")
        
        return close_cols, date_info

    def is_valid_price_column(self, series):
        """检查列是否是有效的价格数据"""
        if series.empty:
            return False
        
        if not pd.api.types.is_numeric_dtype(series):
            try:
                series_numeric = pd.to_numeric(series, errors='coerce')
                if series_numeric.isna().all():
                    return False
            except:
                return False
        
        numeric_series = pd.to_numeric(series, errors='coerce')
        valid_values = numeric_series.dropna()
        if len(valid_values) == 0:
            return False
        
        avg_value = valid_values.mean()
        return 0.1 <= avg_value <= 10000

    def sort_columns_by_date(self, columns, dates):
        """按日期对列进行排序"""
        pairs = list(zip(columns, dates))
        
        def parse_date(date_str):
            try:
                # 尝试多种日期格式
                for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y%m%d", "%Y/%m/%d"):
                    try:
                        return datetime.strptime(date_str, fmt)
                    except:
                        continue
                return datetime(1900, 1, 1)
            except:
                return datetime(1900, 1, 1)
        
        sorted_pairs = sorted(pairs, key=lambda x: parse_date(x[1]))
        
        sorted_columns = [pair[0] for pair in sorted_pairs]
        sorted_dates = [pair[1] for pair in sorted_pairs]
        
        return sorted_columns, sorted_dates

    def calculate_slopes_improved(self, df):
        """改进的斜率计算方法 - 使用7天数据"""
        slopes = {}
        closing_sequences = {}
        date_columns_info = {}
        stock_names = {}
        
        close_cols, date_info = self.find_closing_price_columns(df)
        logging.debug(f"步骤: Found {len(close_cols)} closing price columns: {close_cols}")
        logging.debug(f"步骤: Date info: {date_info}")
        
        if len(close_cols) < 2:
            logging.warning(f"步骤: Not enough closing price columns found. Need at least 2, found {len(close_cols)}")
            for index, row in df.iterrows():
                stock_code = self.get_stock_code(row, df.columns)
                stock_name = self.get_stock_name(row, df.columns)
                key = f"{stock_code} {stock_name}".strip()
                slopes[key] = 0
                closing_sequences[key] = []
                date_columns_info[key] = []
                stock_names[key] = stock_name
            return slopes, closing_sequences, date_columns_info, stock_names
        
        # 只取最近的7天数据
        if len(close_cols) > 7:
            close_cols = close_cols[-7:]
            date_info = date_info[-7:]
            logging.debug(f"步骤: Using last 7 days data: {close_cols}")
            logging.debug(f"步骤: Corresponding dates: {date_info}")
        
        for index, row in df.iterrows():
            stock_code = self.get_stock_code(row, df.columns)
            stock_name = self.get_stock_name(row, df.columns)
            
            closes = []
            valid_dates = []
            
            for i, col in enumerate(close_cols):
                val = row.get(col, np.nan)
                if pd.notna(val):
                    val_str = str(val).replace(',', '').replace('—', '').replace('--', '').strip()
                    if val_str in ["", "NaN", "None", "null"]:
                        continue
                    try:
                        price = float(val_str)
                        if price > 0:
                            closes.append(price)
                            valid_dates.append(date_info[i])
                    except Exception as e:
                        logging.debug(f"步骤: Failed to convert value '{val_str}' to float for column {col}: {str(e)}")
                        continue
            
            logging.debug(f"步骤: Stock {stock_code} {stock_name} - Valid dates: {valid_dates}")
            logging.debug(f"步骤: Stock {stock_code} {stock_name} - Raw prices: {closes}")
            
            key = f"{stock_code} {stock_name}".strip()
            closing_sequences[key] = closes
            date_columns_info[key] = valid_dates
            stock_names[key] = stock_name
            
            if len(closes) < 2:
                logging.debug(f"步骤: Insufficient price data for {stock_code} {stock_name}, only {len(closes)} valid values")
                slopes[key] = 0
                continue
            
            try:
                x = np.arange(len(closes))
                slope, intercept, r_value, p_value, std_err = stats.linregress(x, closes)
                
                avg_price = np.mean(closes)
                slope_percentage = (slope / avg_price) * 100 if avg_price != 0 else 0
                
                slopes[key] = slope_percentage
                logging.debug(f"步骤: Calculated slope for {key}: {slope_percentage:.4f}% (slope={slope:.4f}, avg_price={avg_price:.4f})")
                
            except Exception as e:
                logging.warning(f"步骤: Failed to calculate slope for {stock_code} {stock_name}: {str(e)}")
                slopes[key] = 0
    
        return slopes, closing_sequences, date_columns_info, stock_names

    def read_iwencai_csv_improved(self, file_path):
        """改进的CSV读取方法"""
        try:
            encodings = ['gbk', 'utf-8', 'gb2312', 'utf-8-sig']
            
            for encoding in encodings:
                try:
                    df_raw = pd.read_csv(file_path, encoding=encoding, header=None, nrows=10)
                    
                    header_rows = self.detect_header_rows_improved(df_raw)
                    
                    if header_rows == 1:
                        df = pd.read_csv(file_path, encoding=encoding, header=0)
                    else:
                        df = self.process_double_header_csv_improved(file_path, encoding, header_rows)
                    
                    df = self.basic_data_cleaning(df)
                    return df
                    
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    logging.debug(f"Failed to read CSV with encoding {encoding}: {str(e)}")
                    continue
            
            return pd.read_csv(file_path)
            
        except Exception as e:
            logging.error(f"Error reading improved CSV: {str(e)}")
            return None

    def process_double_header_csv_improved(self, file_path, encoding, header_rows):
        """处理CSV的双表头 - 改进版本"""
        try:
            df_raw = pd.read_csv(file_path, encoding=encoding, header=None)
            header_df = df_raw.iloc[:header_rows].ffill(axis=1)
            df = df_raw.iloc[header_rows:].reset_index(drop=True)
            
            columns = []
            current_prefix = ""
            
            for col in header_df.values.T:
                col_strs = [str(x).strip() for x in col if str(x) != "nan"]
                if len(col_strs) == 0:
                    columns.append("")
                    continue
                    
                if "收盘价" in col_strs[0]:
                    current_prefix = "收盘价"
                elif "5日均线" in col_strs[0] or "均线" in col_strs[0]:
                    current_prefix = "5日均线"
                elif "开盘价" in col_strs[0]:
                    current_prefix = "开盘价"
                elif "财务诊断评分" in col_strs[0]:
                    current_prefix = "财务诊断评分"
                
                date_part = col_strs[-1] if len(col_strs) > 1 else col_strs[0]
                
                if current_prefix and "undefined" in col_strs[0]:
                    merged = f"{current_prefix}_{date_part}"
                else:
                    merged = "_".join(col_strs).strip("_")
                
                columns.append(merged)
            
            df.columns = columns
            return df
            
        except Exception as e:
            logging.error(f"Error processing double header CSV improved: {str(e)}")
            return pd.read_csv(file_path, encoding=encoding, header=1)

    def auto_detect_iwencai_file_improved(self, file_path):
        """改进的自动文件检测"""
        try:
            df = self.read_iwencai_excel_improved(file_path)
            if df is not None and not df.empty:
                return df
            
            df = self.read_iwencai_csv_improved(file_path)
            if df is not None and not df.empty:
                return df
                
            return None
        except Exception as e:
            logging.error(f"Auto detect improved failed: {str(e)}")
            return None

    def identify_stock_columns(self, df):
        """识别股票代码和名称列"""
        df_clean = df.copy()
        
        code_patterns = ['代码', 'code', 'symbol']
        for col in df_clean.columns:
            col_lower = str(col).lower()
            if any(pattern in col_lower for pattern in code_patterns):
                df_clean = df_clean.rename(columns={col: '股票代码'})
                break
        
        name_patterns = ['名称', 'name', '股票名称', '股票简称']
        for col in df_clean.columns:
            col_lower = str(col).lower()
            if any(pattern in col_lower for pattern in name_patterns):
                df_clean = df_clean.rename(columns={col: '股票名称'})
                break
        
        return df_clean

    def get_stock_code(self, row, columns):
        code_keywords = ['代码', 'code', 'symbol', '股票代码']
        for col in columns:
            if any(keyword in str(col).lower() for keyword in code_keywords):
                return str(row[col]) if pd.notna(row[col]) else f"代码{row.name}"
        return f"代码{row.name}"

    def get_stock_name(self, row, columns):
        name_keywords = ['名称', 'name', '股票名称', '股票简称']
        for col in columns:
            if any(keyword in str(col).lower() for keyword in name_keywords):
                return str(row[col]) if pd.notna(row[col]) else f"股票{row.name}"
        return f"股票{row.name}"

    # ==================== 监控控制方法 ====================
    def start_monitoring(self, interval_minutes=5):
        if self.is_monitoring:
            st.warning("监控已在运行")
            return
        self.monitoring_interval = interval_minutes
        self.is_monitoring = True
        self.cycle_count = 1
        st.success(f"监控启动，每{interval_minutes}分钟执行一次")
        self.execute_monitoring_cycle(st.session_state.search_query)
        self.next_execution_time = self.last_execution_time + timedelta(minutes=interval_minutes)

    def stop_monitoring(self):
        self.is_monitoring = False
        self.next_execution_time = None
        st.success("监控已停止")

    def execute_monitoring_cycle(self, search_query):
        try:
            cycle_start = datetime.now()
            self.last_execution_time = cycle_start
            success = self.one_click_automation_with_refresh(search_query)
            if success:
                data = self.process_downloaded_data()
                if data:
                    self.monitoring_data['timestamps'].append(data['timestamp'])
                    self.monitoring_data['stock_counts'].append(data['stock_count'])
                    self.monitoring_data['stock_lists'].append(data['stock_list'])
                    self.monitoring_data['slope_data'].append(data['slopes'])
                    self.monitoring_data['closing_sequences'].append(data['closing_sequences'])
                    self.monitoring_data['date_columns'].append(data['date_columns'])
                    self.monitoring_data['stock_names'].append(data['stock_names'])
                    self.monitoring_data['new_stocks'].append(data['new_stocks'])
                    return True
            return False
        except Exception as e:
            logging.error(f"Error in monitoring cycle: {str(e)}")
            return False

    def update_countdown(self):
        if self.next_execution_time and self.is_monitoring:
            now = datetime.now()
            if now < self.next_execution_time:
                self.countdown_seconds = int((self.next_execution_time - now).total_seconds())
                return True
        self.countdown_seconds = 0
        return False

    def get_countdown_display(self):
        if self.countdown_seconds > 0:
            m = self.countdown_seconds // 60
            s = self.countdown_seconds % 60
            return f"{m:02d}:{s:02d}"
        return "00:00"

    def create_stock_count_chart(self):
        if len(self.monitoring_data['timestamps']) < 1:
            st.info("暂无数据，请先执行一键自动化测试")
            return
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=self.monitoring_data['timestamps'],
            y=self.monitoring_data['stock_counts'],
            mode='lines+markers',
            name='股票数量',
            line=dict(color='blue', width=2),
            marker=dict(size=8)
        ))
        fig.update_layout(
            title='股票数量时间序列',
            xaxis_title='时间',
            yaxis_title='股票数量',
            template='plotly_white',
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)

    def create_slope_chart(self):
        if not self.monitoring_data['slope_data']:
            st.info("暂无斜率数据")
            return
        latest_slopes = self.monitoring_data['slope_data'][-1]
        if not latest_slopes:
            return
        sorted_slopes = sorted(latest_slopes.items(), key=lambda x: x[1], reverse=True)
        top_stocks = sorted_slopes[:20]
        if not top_stocks:
            return
        stocks = [item[0] for item in top_stocks]
        slopes = [item[1] for item in top_stocks]
        colors = ['red' if s < 0 else 'green' for s in slopes]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=slopes,
            y=stocks,
            orientation='h',
            marker_color=colors,
            text=[f"{s:.2f}%" for s in slopes],
            textposition='auto'
        ))
        fig.update_layout(
            title='股票走势斜率排序（前20名）- 7天斜率',
            xaxis_title='斜率(%)',
            yaxis_title='股票',
            template='plotly_white',
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)

    def create_individual_stock_trend_charts(self):
        """为每个股票创建单独的走势图 - 使用改进的日期处理"""
        if (not self.monitoring_data['slope_data'] or 
            not self.monitoring_data['closing_sequences'] or
            not self.monitoring_data['date_columns'] or
            not self.monitoring_data['stock_names'] or
            not self.monitoring_data['new_stocks']):
            st.info("暂无走势数据")
            return
        
        latest_slopes = self.monitoring_data['slope_data'][-1]
        latest_sequences = self.monitoring_data['closing_sequences'][-1]
        latest_dates = self.monitoring_data['date_columns'][-1]
        latest_stock_names = self.monitoring_data['stock_names'][-1]
        latest_new_stocks = self.monitoring_data['new_stocks'][-1]
        
        if not latest_slopes or not latest_sequences or not latest_dates or not latest_stock_names or not latest_new_stocks:
            return
        
        sorted_slopes = sorted(latest_slopes.items(), key=lambda x: x[1], reverse=True)
        top_stocks = sorted_slopes[:20]
        
        if not top_stocks:
            return
        
        st.subheader("斜率前20股票走势图 - 7天数据")
        
        for i, (stock, slope) in enumerate(top_stocks):
            if stock in latest_sequences and stock in latest_dates and stock in latest_stock_names:
                price_sequence = latest_sequences[stock]
                date_sequence = latest_dates[stock]
                stock_name = latest_stock_names[stock]
                
                # 检查是否是新增股票
                is_new_stock = stock in latest_new_stocks
                
                if len(price_sequence) >= 2 and len(date_sequence) == len(price_sequence):
                    # 改进的日期处理：确保日期按正确顺序排列且只包含交易日
                    try:
                        # 将日期字符串转换为datetime对象进行排序
                        date_objs = []
                        valid_prices = []
                        
                        for date_str, price in zip(date_sequence, price_sequence):
                            try:
                                # 尝试多种日期格式
                                date_obj = None
                                for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
                                    try:
                                        date_obj = datetime.strptime(date_str, fmt)
                                        break
                                    except:
                                        continue
                                
                                if date_obj:
                                    # 检查是否为交易日（排除周六周日）
                                    if date_obj.weekday() < 5:  # 0-4表示周一到周五
                                        date_objs.append(date_obj)
                                        valid_prices.append(price)
                                    else:
                                        logging.debug(f"跳过非交易日: {date_str}")
                                else:
                                    logging.warning(f"无法解析日期: {date_str}")
                            except Exception as e:
                                logging.warning(f"日期解析错误 {date_str}: {str(e)}")
                                continue
                        
                        # 如果成功解析了日期，按日期排序
                        if len(date_objs) > 0:
                            # 按日期排序（从早到晚）
                            sorted_data = sorted(zip(date_objs, valid_prices))
                            sorted_dates = [date.strftime('%Y-%m-%d') for date, _ in sorted_data]
                            sorted_prices = [price for _, price in sorted_data]
                            
                            # 确保只显示7个交易日的数据
                            if len(sorted_dates) > 7:
                                sorted_dates = sorted_dates[-7:]
                                sorted_prices = sorted_prices[-7:]
                            
                            date_sequence = sorted_dates
                            price_sequence = sorted_prices
                            logging.debug(f"步骤: Successfully processed dates for {stock}: {date_sequence}")
                        else:
                            # 如果日期解析失败，使用原始顺序但记录警告
                            logging.warning(f"步骤: Date parsing incomplete for {stock}, using original order")
                            st.warning(f"股票 {stock} 的日期数据不完整，可能影响图表显示")
                    except Exception as e:
                        logging.warning(f"Failed to process dates for {stock}: {str(e)}")
                        # 出错时保持原始顺序
                    
                    # 创建折线图
                    fig = go.Figure()
                    
                    # 主价格线
                    fig.add_trace(go.Scatter(
                        x=date_sequence,
                        y=price_sequence,
                        mode='lines+markers+text',
                        name=f"{stock}",
                        line=dict(color='#1f77b4', width=3),
                        marker=dict(size=8, color='#ff7f0e'),
                        text=[f"{price:.2f}" for price in price_sequence],
                        textposition="top center",
                        hovertemplate='<b>%{x}</b><br>收盘价: %{y:.2f}元<extra></extra>'
                    ))
                    
                    # 添加趋势线
                    if len(price_sequence) >= 2:
                        try:
                            x_numeric = np.arange(len(price_sequence))
                            slope_val, intercept, _, _, _ = stats.linregress(x_numeric, price_sequence)
                            trend_line = intercept + slope_val * x_numeric
                            
                            fig.add_trace(go.Scatter(
                                x=date_sequence,
                                y=trend_line,
                                mode='lines',
                                name='趋势线',
                                line=dict(color='red', width=2, dash='dash'),
                                opacity=0.7
                            ))
                        except Exception as e:
                            logging.debug(f"Failed to add trend line for {stock}: {str(e)}")
                    
                    # 计算价格范围用于设置Y轴
                    price_min = min(price_sequence) if price_sequence else 0
                    price_max = max(price_sequence) if price_sequence else 0
                    price_range = price_max - price_min
                    y_padding = price_range * 0.1 if price_range > 0 else (price_min * 0.1 if price_min > 0 else 1)
                    
                    # 更新布局，在标题中包含股票简称和新股票标记
                    title = f"<b>{stock}</b> - {stock_name} - 7天斜率: {slope:.2f}%"
                    if is_new_stock:
                        title += " 🆕"  # 添加新股票标记
                    
                    fig.update_layout(
                        title=title,
                        xaxis_title='<b>日期</b>',
                        yaxis_title='<b>收盘价(元)</b>',
                        template='plotly_white',
                        height=400,
                        showlegend=True,
                        xaxis=dict(
                            tickangle=45,
                            # 使用category类型确保正确显示日期
                            type='category',
                            # 确保x轴按时间顺序显示
                            categoryorder='array',
                            categoryarray=date_sequence
                        ),
                        yaxis=dict(
                            range=[price_min - y_padding, price_max + y_padding] if price_sequence else [0, 10]
                        ),
                        hovermode='x unified'
                    )
                    
                    # 显示图表
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 显示股票统计数据
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        if price_sequence:
                            st.metric("最新价格", f"{price_sequence[-1]:.2f}元")
                        else:
                            st.metric("最新价格", "N/A")
                    with col2:
                        if is_new_stock:
                            st.metric("股票简称", f"{stock_name} 🆕")  # 新股票标记
                        else:
                            st.metric("股票简称", stock_name)
                    with col3:
                        if price_sequence and price_sequence[0] != 0:
                            change_percent = (price_sequence[-1] - price_sequence[0]) / price_sequence[0] * 100
                            st.metric("涨跌幅", f"{change_percent:.2f}%")
                        else:
                            st.metric("涨跌幅", "N/A")
                    with col4:
                        st.metric("数据点数", len(price_sequence))
                    
                    # 显示日期范围信息
                    if len(date_sequence) >= 2:
                        st.info(f"数据时间范围: {date_sequence[0]} 至 {date_sequence[-1]} (共{len(date_sequence)}个交易日)")
                    elif len(date_sequence) == 1:
                        st.info(f"数据时间: {date_sequence[0]} (共{len(date_sequence)}个交易日)")
                    else:
                        st.warning("无有效交易日数据")
                    
                    # 在图表之间添加分隔线（除了最后一个）
                    if i < len(top_stocks) - 1:
                        st.markdown("---")
                else:
                    st.warning(f"股票 {stock} 的数据不完整，无法绘制走势图")
            else:
                st.warning(f"股票 {stock} 缺少价格、日期或名称数据")

    def show_monitoring_dashboard(self):
        st.header("监控仪表板")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("监控数据点", len(self.monitoring_data['timestamps']))
        with col2:
            if self.monitoring_data['stock_counts']:
                st.metric("最新股票数量", self.monitoring_data['stock_counts'][-1])
            else:
                st.metric("最新股票数量", 0)
        with col3:
            if self.monitoring_data['timestamps']:
                st.metric("最后更新时间", self.monitoring_data['timestamps'][-1].strftime("%H:%M:%S"))
            else:
                st.metric("最后更新时间", "无数据")
        with col4:
            if self.is_monitoring:
                self.update_countdown()
                countdown_display = self.get_countdown_display()
                st.metric("下次执行倒计时", countdown_display)
            else:
                st.metric("监控状态", "已停止")
        
        # 显示新出现股票的信息
        if self.monitoring_data['new_stocks'] and len(self.monitoring_data['new_stocks']) > 0:
            latest_new_stocks = self.monitoring_data['new_stocks'][-1]
            if latest_new_stocks:
                st.subheader("🎉 新出现股票")
                st.info(f"本次刷新发现了 {len(latest_new_stocks)} 只新股票")
                for i, stock in enumerate(latest_new_stocks):
                    st.success(f"{i+1}. {stock}")
        
        self.create_stock_count_chart()
        
        col1, col2 = st.columns(2)
        with col1:
            self.create_slope_chart()
        with col2:
            st.subheader("股票走势分析")
            st.info("下方将显示每个股票的详细走势图，基于7天收盘价计算斜率")
            st.info("🆕 标记表示新出现的股票")
            st.info("📈 时间轴已按正确的时间顺序排列，不含周六周日")
        
        self.create_individual_stock_trend_charts()
        
        if self.monitoring_data['stock_lists']:
            st.subheader("最新股票列表")
            latest_df = self.monitoring_data['stock_lists'][-1]
            
            # 标记新出现的股票
            if self.monitoring_data['new_stocks'] and len(self.monitoring_data['new_stocks']) > 0:
                latest_new_stocks = self.monitoring_data['new_stocks'][-1]
                
                # 创建显示用的DataFrame，添加新股票标记
                display_df = latest_df.copy()
                
                # 添加新股票标记列
                display_df['是否新股票'] = ''
                for index, row in display_df.iterrows():
                    stock_code = self.get_stock_code(row, display_df.columns)
                    stock_name = self.get_stock_name(row, display_df.columns)
                    stock_key = f"{stock_code} {stock_name}".strip()
                    if stock_key in latest_new_stocks:
                        display_df.at[index, '是否新股票'] = '🆕'
                
                st.dataframe(display_df, use_container_width=True)
            else:
                st.dataframe(latest_df, use_container_width=True)
            
            with st.expander("数据统计信息"):
                st.write(f"总股票数: {len(latest_df)}")
                st.write(f"数据列数: {len(latest_df.columns)}")
                
                numeric_cols = latest_df.select_dtypes(include=[np.number]).columns.tolist()
                if numeric_cols:
                    st.write("数值列统计:")
                    st.dataframe(latest_df[numeric_cols].describe(), use_container_width=True)

    def close(self):
        self.stop_monitoring()
        if self.driver:
            self.driver.quit()
        if os.path.exists(self.profile_dir):
            shutil.rmtree(self.profile_dir)

# ====================== 数据导出功能 ======================
def add_export_functionality(monitor):
    """添加数据导出功能"""
    st.sidebar.subheader("数据导出")
    
    if monitor.monitoring_data['stock_lists']:
        latest_data = monitor.monitoring_data['stock_lists'][-1]
        
        csv_data = latest_data.to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button(
            label="导出CSV",
            data=csv_data,
            file_name=f"stock_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
        
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            latest_data.to_excel(writer, index=False, sheet_name='股票数据')
        st.sidebar.download_button(
            label="导出Excel",
            data=excel_buffer.getvalue(),
            file_name=f"stock_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ====================== 主函数 ======================
def main():
    if 'monitor' not in st.session_state:
        st.session_state.monitor = StockMonitor()
    if 'search_query' not in st.session_state:
        st.session_state.search_query = "2025年11月12日收盘价大于5日均线，2025年11月13日收盘价大于5日均线，2025年11月14日收盘价大于5日均线，2025年11月17日收盘价大于5日均线，2025年11月18日收盘价大于5日均线，2025年11月19日收盘价大于5日均线，2025年11月20日收盘价大于5日均线，非ST，非北交所，财务综合评分大于2.5"  # 修改为7个交易日
    
    st.sidebar.title("控制面板")
    
    st.sidebar.subheader("固化匹配状态")
    cache_data = []
    for element_type, cache_info in st.session_state.monitor.cached_selectors.items():
        if cache_info:
            cache_data.append({
                '元素类型': element_type,
                '选择器': cache_info['selector'],
                '描述': cache_info['description']
            })
        else:
            cache_data.append({
                '元素类型': element_type,
                '选择器': '未缓存',
                '描述': '未缓存'
            })
    st.sidebar.dataframe(pd.DataFrame(cache_data), use_container_width=True)
    
    st.sidebar.subheader("搜索设置")
    search_query = st.sidebar.text_area("搜索查询", value=st.session_state.search_query, height=100)
    if search_query != st.session_state.search_query:
        st.session_state.search_query = search_query
        st.sidebar.success("搜索查询已更新")
    
    if st.sidebar.button("一键自动化测试", type="primary"):
        with st.spinner("执行一键自动化测试..."):
            if st.session_state.monitor.one_click_automation_with_refresh(st.session_state.search_query):
                data = st.session_state.monitor.process_downloaded_data()
                if data:
                    st.session_state.monitor.monitoring_data['timestamps'].append(data['timestamp'])
                    st.session_state.monitor.monitoring_data['stock_counts'].append(data['stock_count'])
                    st.session_state.monitor.monitoring_data['stock_lists'].append(data['stock_list'])
                    st.session_state.monitor.monitoring_data['slope_data'].append(data['slopes'])
                    st.session_state.monitor.monitoring_data['closing_sequences'].append(data['closing_sequences'])
                    st.session_state.monitor.monitoring_data['date_columns'].append(data['date_columns'])
                    st.session_state.monitor.monitoring_data['stock_names'].append(data['stock_names'])
                    st.session_state.monitor.monitoring_data['new_stocks'].append(data['new_stocks'])
                    st.success("一键自动化测试成功")
                else:
                    st.error("数据处理失败")
            else:
                st.error("一键自动化测试失败")
    
    st.sidebar.subheader("自动监控")
    interval = st.sidebar.slider("监控间隔(分钟)", 1, 30, 5)
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("开始监控", type="primary"):
            if not st.session_state.monitor.is_monitoring:
                st.session_state.monitor.start_monitoring(interval)
            else:
                st.warning("监控已在运行")
    with col2:
        if st.button("停止监控"):
            st.session_state.monitor.stop_monitoring()
    
    if st.session_state.monitor.is_monitoring:
        st.sidebar.success("监控运行中")
        if st.session_state.monitor.next_execution_time:
            st.sidebar.info(f"下次执行时间: {st.session_state.monitor.next_execution_time.strftime('%H:%M:%S')}")
    else:
        st.sidebar.info("监控已停止")
    
    add_export_functionality(st.session_state.monitor)
    
    st.session_state.monitor.show_monitoring_dashboard()
    
    with st.expander("使用说明"):
        st.markdown("""
        ### 系统特性
        - **7天斜率计算**: 基于最近7个交易日的收盘价计算股票走势斜率
        - **新股票识别**: 每次刷新自动识别新出现的股票并标记
        - **双表头优化**: 专门优化同花顺双表头格式，自动处理undefined字段
        - **智能列名**: 遇到undefined字段时，自动使用另一行的值来命名
        - **股票简称显示**: 在折线图标题和第二列中显示股票简称
        - **日期匹配**: 自动匹配收盘价列与对应日期，确保走势图横坐标显示正确日期
        - **时间轴优化**: 坐标轴按正确的时间顺序排列，以一天为单位，不含周六周日
        - **实时监控**: 可设置定时自动执行
        - **数据导出**: 支持CSV和Excel格式导出
        
        ### 7天斜率计算
        - 系统会自动获取最近7个交易日的收盘价数据
        - 使用线性回归计算这7天的价格趋势斜率
        - 斜率以百分比形式显示，表示价格变化的趋势强度
        
        ### 时间轴优化
        - 自动识别和解析日期格式
        - 按时间先后顺序正确排列坐标轴
        - 确保时间序列正确显示，不含周六周日
        - 显示完整的时间范围信息
        
        ### 新股票识别
        - 系统会自动比较当前和上一次的股票列表
        - 新出现的股票会在图表标题和股票列表中标记为 🆕
        - 在监控仪表板顶部会显示新出现股票的数量和列表
        
        ### 操作步骤
        1. 点击"一键自动化测试"进行首次测试
        2. 设置监控间隔时间
        3. 点击"开始监控"启动自动监控
        4. 系统会定期自动执行并更新数据
        5. 使用侧边栏的数据导出功能下载数据
        """)
    
    st.sidebar.markdown("---")
    if st.sidebar.button("关闭系统"):
        st.session_state.monitor.close()
        st.sidebar.success("系统已关闭")
    
    if st.session_state.monitor.is_monitoring:
        now = datetime.now()
        if now >= st.session_state.monitor.next_execution_time:
            st.session_state.monitor.execute_monitoring_cycle(st.session_state.search_query)
            st.session_state.monitor.cycle_count += 1
            st.session_state.monitor.next_execution_time = datetime.now() + timedelta(minutes=st.session_state.monitor.monitoring_interval)
        st.session_state.monitor.update_countdown()
        time.sleep(1)
        st.rerun()

if __name__ == "__main__":
    main()