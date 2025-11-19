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
warnings.filterwarnings('ignore')

# 设置 logging 配置
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# ====================== 页面配置 ======================
st.set_page_config(
    page_title="同花顺问财监控系统",
    page_icon="📈",
    layout="wide"
)
st.title("同花顺问财股票监控系统")
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
            'slope_data': []
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
            # 首先尝试使用 Chrome
            return self.initialize_chrome_with_manager()
        except Exception as e:
            logging.error(f"Chrome initialization failed: {str(e)}")
            try:
                # 如果 Chrome 失败，尝试 Edge
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
            
            # 简化导航逻辑
            if force_refresh:
                logging.debug(f"步骤: Force refreshing to {target_url}")
                self.driver.get(target_url)
            else:
                current_url = self.driver.current_url
                if target_url not in current_url:
                    logging.debug(f"步骤: Navigating to {target_url}")
                    self.driver.get(target_url)
            
            # 更宽松的等待条件
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
            
            # 简化的登录检测
            login_indicators = [
                "//div[contains(text(), '扫码登录')]",
                "//div[contains(@class, 'login')]",
                "//div[contains(@class, 'qrcode')]",
            ]
            
            # 快速检查
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
            # 检查登录弹窗是否还存在
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
                time.sleep(2)  # 等待页面稳定
                return True
            
            time.sleep(2)
        
        logging.warning("步骤: Login timeout.")
        return False

    # ==================== 改进的下载流程 ====================
    def smart_download_flow_optimized(self):
        """改进的下载流程"""
        try:
            logging.debug("步骤: Starting optimized download flow...")
            
            # 记录下载开始时间
            download_start_time = time.time()
            
            # 首先清空下载目录的旧文件
            self.clean_download_directory()
            
            # 查找下载按钮
            btn = self.find_and_cache_download_button()
            if not btn:
                logging.error("步骤: Download button not found.")
                # 尝试其他选择器
                btn = self.find_alternative_download_button()
                if not btn:
                    return False
            
            # 点击下载按钮
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
            
            # 处理可能的登录
            time.sleep(3)
            if not self.is_logged_in:
                self.handle_login_smartly()
            
            # 如果登录成功，重新点击下载
            if self.is_logged_in:
                time.sleep(3)
                btn = self.find_and_cache_download_button()
                if btn:
                    try:
                        self.driver.execute_script("arguments[0].click();", btn)
                    except:
                        btn.click()
            
            # 等待下载完成，传递开始时间
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
            # 临时文件扩展名
            temp_extensions = ['.crdownload', '.part', '.tmp', '.temp']
            
            # 记录开始等待的时间
            wait_start_time = time.time()
            
            while time.time() - wait_start_time < timeout:
                try:
                    files = os.listdir(self.download_dir)
                    logging.debug(f"步骤: Current files in directory: {files}")
                    
                    # 遍历下载目录中的每个文件
                    for file in files:
                        file_path = os.path.join(self.download_dir, file)
                        
                        # 跳过临时文件
                        if any(file.endswith(ext) for ext in temp_extensions):
                            logging.debug(f"步骤: Skipping temp file: {file}")
                            continue
                            
                        # 检查文件大小和修改时间
                        if os.path.getsize(file_path) > 0:
                            # 获取文件的修改时间和创建时间，取最大值
                            mtime = os.path.getmtime(file_path)
                            ctime = os.path.getctime(file_path)
                            file_time = max(mtime, ctime)
                            
                            # 如果文件的时间在开始时间之后，说明是新下载的文件
                            if file_time >= start_time:
                                logging.debug(f"步骤: Download completed with file: {file}")
                                logging.debug(f"步骤: File time: {file_time}, Start time: {start_time}")
                                return True
                            
                            # 如果文件时间早于开始时间，但文件大小有变化，也可能是新下载的（覆盖）
                            file_size = os.path.getsize(file_path)
                            logging.debug(f"步骤: File {file} - Size: {file_size}, Time: {file_time}")
                except Exception as e:
                    logging.error(f"Error checking download directory: {str(e)}")
                
                time.sleep(2)
            
            # 超时后检查是否有任何文件
            files = os.listdir(self.download_dir)
            if files:
                logging.warning(f"步骤: Timeout but found files: {files}")
                # 即使超时，如果有文件也返回成功
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
            
            # 刷新页面
            if not self.ensure_navigation(force_refresh=True):
                return False
            time.sleep(3)
            
            # 搜索操作
            if not self.find_search_box_with_cache(search_query):
                return False
            
            if not self.find_search_button_with_cache():
                return False
            time.sleep(5)
            
            # 下载操作
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

    # ==================== 改进的数据处理方法 - 修复undefined列识别问题 ====================
    def process_downloaded_data(self):
        try:
            logging.debug("步骤: Processing downloaded data...")
            files = os.listdir(self.download_dir)
            logging.debug(f"步骤: All files in download directory: {files}")
            
            if not files:
                logging.warning("步骤: No files in download directory.")
                return None
            
            # 找到最新的文件
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
            
            # 使用改进的方法读取文件
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
            slope_data = self.calculate_slopes_improved(df)
            
            logging.debug(f"步骤: Successfully processed {stock_count} stocks")
            
            return {
                'timestamp': datetime.now(),
                'stock_count': stock_count,
                'stock_list': df,
                'slopes': slope_data
            }
        except Exception as e:
            logging.error(f"Error processing data: {str(e)}")
            return None

    def read_iwencai_excel_improved(self, file_path):
        """改进的Excel读取方法，结合两种方法的优势"""
        try:
            # 读取原始数据来分析结构
            df_raw = pd.read_excel(file_path, header=None, nrows=10)
            logging.debug("步骤: Raw Excel data preview:")
            for i in range(min(10, len(df_raw))):
                logging.debug(f"Row {i}: {df_raw.iloc[i].tolist()}")
            
            # 检测表头行数
            header_rows = self.detect_header_rows(df_raw)
            logging.debug(f"步骤: Detected header rows: {header_rows}")
            
            # 根据表头行数读取数据
            if header_rows == 1:
                # 单行表头
                df = pd.read_excel(file_path, header=0)
                df.columns = [str(c).strip() for c in df.columns]
            else:
                # 多行表头 - 使用您提供的方法
                df_raw_full = pd.read_excel(file_path, header=None)
                header_df = df_raw_full.iloc[:header_rows].ffill(axis=1)
                
                # 构建合并列名
                columns = []
                current_prefix = ""
                for col in header_df.values.T:
                    col_strs = [str(x).strip() for x in col if str(x) != "nan"]
                    if len(col_strs) == 0:
                        columns.append("")
                        continue
                    
                    # 识别列类别
                    if "收盘价" in col_strs[0]:
                        current_prefix = "收盘价"
                    elif "5日均线" in col_strs[0] or "均线" in col_strs[0]:
                        current_prefix = "5日均线"
                    
                    # 提取日期部分
                    date_part = col_strs[-1] if len(col_strs) > 1 else col_strs[0]
                    
                    # 构建列名
                    if current_prefix and "undefined" in col_strs[0]:
                        merged = f"{current_prefix}_{date_part}"
                    else:
                        merged = "_".join(col_strs).strip("_")
                    columns.append(merged)
                
                # 读取数据部分
                df = df_raw_full.iloc[header_rows:].reset_index(drop=True)
                df.columns = columns
            
            # 基础数据清洗
            df = self.basic_data_cleaning(df)
            
            logging.debug(f"步骤: Final columns after processing: {list(df.columns)}")
            return df
            
        except Exception as e:
            logging.error(f"Error reading improved Excel: {str(e)}")
            # 备用方法
            return pd.read_excel(file_path)

    def detect_header_rows(self, df_preview):
        """检测表头行数"""
        header_keywords = ['代码', '名称', '收盘价', '财务诊断评分', '概念']
        
        for i in range(min(5, len(df_preview))):
            row_text = ' '.join([str(x) for x in df_preview.iloc[i] if pd.notna(x)])
            # 检查是否包含表头关键词
            if any(keyword in row_text for keyword in header_keywords):
                # 如果是第一行就包含关键词，可能是单行表头
                if i == 0:
                    return 1
                # 否则返回检测到的行号（从0开始）
                return i + 1
        
        # 默认返回1（单行表头）
        return 1

    def basic_data_cleaning(self, df):
        """基础数据清洗"""
        if df is None or df.empty:
            return df
        
        df_clean = df.copy()
        
        # 清理字符串列
        for col in df_clean.select_dtypes(include=['object']).columns:
            try:
                df_clean[col] = df_clean[col].astype(str).str.strip().replace({
                    'nan': np.nan, 'None': np.nan, '': np.nan
                })
            except Exception:
                pass
        
        # 替换各种空值符号
        replace_symbols = ["-", "—", "空值", "null", "None", "", "NaN", "--"]
        df_clean.replace(replace_symbols, np.nan, inplace=True)
        
        # 处理数值列
        for col in df_clean.columns:
            if df_clean[col].dtype == object:
                try:
                    # 移除逗号和空格
                    df_clean[col] = df_clean[col].astype(str).str.replace(',', '').str.replace(' ', '')
                except Exception:
                    pass
                try:
                    # 尝试转换为数值
                    df_clean[col] = pd.to_numeric(df_clean[col], errors='ignore')
                except Exception:
                    pass
        
        # 移除完全空白的行和列
        df_clean = df_clean.dropna(how='all')
        df_clean = df_clean.dropna(axis=1, how='all')
        
        # 识别股票代码和名称列
        df_clean = self.identify_stock_columns(df_clean)
        
        return df_clean

    def find_closing_price_columns(self, df):
        """查找收盘价列，包括undefined列"""
        close_cols = []
        
        # 首先查找明确的收盘价列
        closing_keywords = ['收盘价', 'close', 'price']
        for col in df.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in closing_keywords):
                # 检查是否是数值列
                if pd.api.types.is_numeric_dtype(df[col]):
                    close_cols.append(col)
                else:
                    # 尝试转换为数值
                    try:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                        if not df[col].isna().all():
                            close_cols.append(col)
                    except:
                        pass
        
        # 专门查找undefined列（这些也是收盘价数据）
        for col in df.columns:
            col_str = str(col).lower()
            if 'undefined' in col_str:
                # 检查是否是数值列
                if pd.api.types.is_numeric_dtype(df[col]):
                    close_cols.append(col)
                else:
                    # 尝试转换为数值
                    try:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                        if not df[col].isna().all():
                            close_cols.append(col)
                    except:
                        pass
        
        # 如果收盘价列不够，查找包含日期的数值列
        if len(close_cols) < 2:
            date_pattern = r'\d{4}\.\d{2}\.\d{2}|\d{4}-\d{2}-\d{2}|\d{8}'
            for col in df.columns:
                col_str = str(col)
                if re.search(date_pattern, col_str) and pd.api.types.is_numeric_dtype(df[col]):
                    close_cols.append(col)
        
        # 按列位置排序，确保正确的顺序（从左到右，最近的日期在最右边）
        close_cols.sort(key=lambda x: list(df.columns).index(x))
        
        logging.debug(f"步骤: Final closing price columns found: {close_cols}")
        return close_cols

    def calculate_slopes_improved(self, df):
        """改进的斜率计算方法，增加详细调试信息"""
        slopes = {}
        
        # 查找收盘价列
        close_cols = self.find_closing_price_columns(df)
        logging.debug(f"步骤: Found {len(close_cols)} closing price columns: {close_cols}")
        
        if len(close_cols) < 2:
            logging.warning(f"步骤: Not enough closing price columns found. Need at least 2, found {len(close_cols)}")
            # 为每个股票返回0斜率
            for index, row in df.iterrows():
                stock_code = self.get_stock_code(row, df.columns)
                stock_name = self.get_stock_name(row, df.columns)
                key = f"{stock_code} {stock_name}".strip()
                slopes[key] = 0
            return slopes
        
        # 对每个股票计算斜率
        for index, row in df.iterrows():
            stock_code = self.get_stock_code(row, df.columns)
            stock_name = self.get_stock_name(row, df.columns)
            
            # 提取收盘价序列
            closes = []
            valid_columns = []
            
            for col in close_cols:
                val = row.get(col, np.nan)
                if pd.notna(val):
                    # 清理数值
                    val_str = str(val).replace(',', '').replace('—', '').replace('--', '').strip()
                    if val_str in ["", "NaN", "None", "null"]:
                        continue
                    try:
                        price = float(val_str)
                        if price > 0:
                            closes.append(price)
                            valid_columns.append(col)
                    except Exception as e:
                        logging.debug(f"步骤: Failed to convert value '{val_str}' to float for column {col}: {str(e)}")
                        continue
            
            logging.debug(f"步骤: Stock {stock_code} {stock_name} - Valid columns: {valid_columns}")
            logging.debug(f"步骤: Stock {stock_code} {stock_name} - Raw prices: {closes}")
            
            # 检查是否有足够的数据点
            if len(closes) < 2:
                logging.debug(f"步骤: Insufficient price data for {stock_code} {stock_name}, only {len(closes)} valid values")
                key = f"{stock_code} {stock_name}".strip()
                slopes[key] = 0
                continue
            
            # 反转顺序（从旧到新）- 因为同花顺的数据通常是最近的日期在右边
            closes = closes[::-1]
            logging.debug(f"步骤: Stock {stock_code} {stock_name} - Reversed prices (old to new): {closes}")
            
            # 计算斜率
            try:
                x = np.arange(len(closes))
                slope, intercept, r_value, p_value, std_err = stats.linregress(x, closes)
                
                # 计算斜率百分比（相对于平均值）
                avg_price = np.mean(closes)
                slope_percentage = (slope / avg_price) * 100 if avg_price != 0 else 0
                
                key = f"{stock_code} {stock_name}".strip()
                slopes[key] = slope_percentage
                logging.debug(f"步骤: Calculated slope for {key}: {slope_percentage:.4f}% (slope={slope:.4f}, avg_price={avg_price:.4f})")
                
            except Exception as e:
                logging.warning(f"步骤: Failed to calculate slope for {stock_code} {stock_name}: {str(e)}")
                key = f"{stock_code} {stock_name}".strip()
                slopes[key] = 0
    
        return slopes

    def read_iwencai_csv_improved(self, file_path):
        """改进的CSV读取方法"""
        try:
            # 尝试多种编码
            encodings = ['gbk', 'utf-8', 'gb2312', 'utf-8-sig']
            
            for encoding in encodings:
                try:
                    # 读取原始数据
                    df_raw = pd.read_csv(file_path, encoding=encoding, header=None, nrows=10)
                    
                    # 检测表头行数
                    header_rows = self.detect_header_rows(df_raw)
                    
                    if header_rows == 1:
                        df = pd.read_csv(file_path, encoding=encoding, header=0)
                    else:
                        # 多行表头处理
                        df_raw_full = pd.read_csv(file_path, encoding=encoding, header=None)
                        header_df = df_raw_full.iloc[:header_rows].ffill(axis=1)
                        
                        # 构建合并列名（与Excel方法相同）
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
                            
                            date_part = col_strs[-1] if len(col_strs) > 1 else col_strs[0]
                            
                            if current_prefix and "undefined" in col_strs[0]:
                                merged = f"{current_prefix}_{date_part}"
                            else:
                                merged = "_".join(col_strs).strip("_")
                            columns.append(merged)
                        
                        df = df_raw_full.iloc[header_rows:].reset_index(drop=True)
                        df.columns = columns
                    
                    # 基础数据清洗
                    df = self.basic_data_cleaning(df)
                    return df
                    
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    logging.debug(f"Failed to read CSV with encoding {encoding}: {str(e)}")
                    continue
            
            # 所有编码都失败，尝试默认读取
            return pd.read_csv(file_path)
            
        except Exception as e:
            logging.error(f"Error reading improved CSV: {str(e)}")
            return None

    def auto_detect_iwencai_file_improved(self, file_path):
        """改进的自动文件检测"""
        try:
            # 尝试Excel
            df = self.read_iwencai_excel_improved(file_path)
            if df is not None and not df.empty:
                return df
            
            # 尝试CSV
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
        
        # 查找代码列
        code_patterns = ['代码', 'code', 'symbol']
        for col in df_clean.columns:
            col_lower = str(col).lower()
            if any(pattern in col_lower for pattern in code_patterns):
                df_clean = df_clean.rename(columns={col: '股票代码'})
                break
        
        # 查找名称列
        name_patterns = ['名称', 'name', '股票名称']
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
        name_keywords = ['名称', 'name', '股票名称']
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
            text=[f"{s:.4f}" for s in slopes],
            textposition='auto'
        ))
        fig.update_layout(
            title='股票走势斜率排序（前20名）',
            xaxis_title='斜率(%)',
            yaxis_title='股票',
            template='plotly_white',
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)

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
        
        self.create_stock_count_chart()
        self.create_slope_chart()
        
        if self.monitoring_data['stock_lists']:
            st.subheader("最新股票列表")
            latest_df = self.monitoring_data['stock_lists'][-1]
            st.dataframe(latest_df.head(10), use_container_width=True)
            
            # 显示调试信息
            with st.expander("详细调试信息"):
                st.write("数据列信息:")
                st.write(f"总列数: {len(latest_df.columns)}")
                st.write("所有列名:")
                for i, col in enumerate(latest_df.columns):
                    st.write(f"{i}: '{col}'")
                
                # 显示找到的收盘价列
                close_cols = self.find_closing_price_columns(latest_df)
                st.write(f"找到的收盘价列 ({len(close_cols)} 个):")
                for i, col in enumerate(close_cols):
                    st.write(f"  {i}: '{col}'")
                
                # 显示前几个股票的详细数据
                st.write("前3个股票的详细收盘价数据:")
                for i in range(min(3, len(latest_df))):
                    row = latest_df.iloc[i]
                    stock_code = self.get_stock_code(row, latest_df.columns)
                    stock_name = self.get_stock_name(row, latest_df.columns)
                    
                    st.write(f"**{stock_code} {stock_name}**:")
                    
                    # 显示所有收盘价列的值
                    price_data = []
                    for col in close_cols:
                        val = row.get(col, np.nan)
                        price_data.append(f"'{col}': {val}")
                    
                    st.write("收盘价数据: " + ", ".join(price_data))
                    
                    # 显示计算出的斜率
                    if self.monitoring_data['slope_data']:
                        latest_slopes = self.monitoring_data['slope_data'][-1]
                        key = f"{stock_code} {stock_name}".strip()
                        slope = latest_slopes.get(key, "未找到")
                        st.write(f"计算出的斜率: {slope}")
                
                # 显示所有股票的斜率
                if self.monitoring_data['slope_data']:
                    latest_slopes = self.monitoring_data['slope_data'][-1]
                    st.write("所有股票的斜率:")
                    slope_data = []
                    for stock, slope in latest_slopes.items():
                        slope_data.append({"股票": stock, "斜率(%)": f"{slope:.4f}%"})
                    
                    if slope_data:
                        slope_df = pd.DataFrame(slope_data)
                        st.dataframe(slope_df, use_container_width=True)

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
        
        # CSV导出
        csv_data = latest_data.to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button(
            label="导出CSV",
            data=csv_data,
            file_name=f"stock_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
        
        # Excel导出
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
        st.session_state.search_query = "下影线＞上影线，去掉st，去掉北交所，5日均线、10日均线、20日、60日均线多头排列，财务综合评分大于2，上升通道，5个交易日每日收盘价"
    
    st.sidebar.title("控制面板")
    
    # 显示缓存状态
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
    
    # 一键自动化测试
    if st.sidebar.button("一键自动化测试", type="primary"):
        with st.spinner("执行一键自动化测试..."):
            if st.session_state.monitor.one_click_automation_with_refresh(st.session_state.search_query):
                data = st.session_state.monitor.process_downloaded_data()
                if data:
                    st.session_state.monitor.monitoring_data['timestamps'].append(data['timestamp'])
                    st.session_state.monitor.monitoring_data['stock_counts'].append(data['stock_count'])
                    st.session_state.monitor.monitoring_data['stock_lists'].append(data['stock_list'])
                    st.session_state.monitor.monitoring_data['slope_data'].append(data['slopes'])
                    st.success("一键自动化测试成功")
                else:
                    st.error("数据处理失败")
            else:
                st.error("一键自动化测试失败")
    
    # 监控控制
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
    
    # 显示监控状态
    if st.session_state.monitor.is_monitoring:
        st.sidebar.success("监控运行中")
        if st.session_state.monitor.next_execution_time:
            st.sidebar.info(f"下次执行时间: {st.session_state.monitor.next_execution_time.strftime('%H:%M:%S')}")
    else:
        st.sidebar.info("监控已停止")
    
    # 添加数据导出功能
    add_export_functionality(st.session_state.monitor)
    
    # 显示监控仪表板
    st.session_state.monitor.show_monitoring_dashboard()
    
    # 使用指南
    with st.expander("使用说明"):
        st.markdown("""
        ### 系统特性
        - **自动驱动管理**: 使用 webdriver-manager 自动下载和管理浏览器驱动
        - **智能登录处理**: 扫码登录后自动检测并继续流程
        - **实时监控**: 可设置定时自动执行
        - **数据导出**: 支持CSV和Excel格式导出
        - **智能数据清洗**: 专门针对同花顺问财的两行表头格式优化
        - **改进的斜率计算**: 准确计算5天内走势的斜率，特别处理undefined列
        
        ### 操作步骤
        1. 点击"一键自动化测试"进行首次测试
        2. 设置监控间隔时间
        3. 点击"开始监控"启动自动监控
        4. 系统会定期自动执行并更新数据
        5. 使用侧边栏的数据导出功能下载数据
        
        ### 注意事项
        - 首次运行会下载浏览器驱动，请保持网络连接
        - 扫码登录后请勿关闭浏览器窗口
        - 如需停止监控，请点击"停止监控"按钮
        - 下载的文件会自动保存在临时目录，可通过导出功能保存到本地
        - 系统专门优化了同花顺问财的两行表头格式处理
        - 系统会自动识别 undefined 列作为收盘价数据用于斜率计算
        - 查看"详细调试信息"展开面板可以了解数据解析和斜率计算的详细过程
        """)
    
    # 关闭系统
    st.sidebar.markdown("---")
    if st.sidebar.button("关闭系统"):
        st.session_state.monitor.close()
        st.sidebar.success("系统已关闭")
    
    # 监控循环
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