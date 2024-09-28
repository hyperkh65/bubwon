import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import urllib.parse
import pandas as pd
import numpy as np
import re
from datetime import datetime

# WebDriver 초기 설정 (headless 모드 추가)
def setup_webdriver():
    try:
        # Chrome 옵션 설정
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Headless 모드
        chrome_options.add_argument("--no-sandbox")  # 샌드박스 모드 비활성화
        chrome_options.add_argument("--disable-dev-shm-usage")  # /dev/shm 사용 비활성화
        chrome_options.add_argument("--disable-gpu")  # GPU 비활성화 (선택적)
        chrome_options.add_argument("--window-size=1920x1080")  # 창 크기 설정 (선택적)

        # WebDriver 설정
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(10)  # 모든 요소를 찾을 때 최대 대기 시간 설정
        return driver
    except Exception as e:
        st.error(f"WebDriver 설정 오류: {e}")
        return None

# 검색 페이지로 이동
def navigate_to_search_page(driver):
    try:
        driver.get("https://www.courtauction.go.kr/")
        driver.switch_to.frame("indexFrame")
        wait = WebDriverWait(driver, 10)
        search_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@id='qk_srch_link_1']/a")))
        search_button.click()
    except Exception as e:
        st.error(f"검색 페이지로 이동 중 오류 발생: {e}")
        driver.quit()

# 검색 조건 설정
def set_search_criteria(driver, input_data, building_codes):
    try:
        # 지원 선택
        setCourt = Select(driver.find_element(By.ID, 'idJiwonNm'))
        setCourt.select_by_value(input_data['jiwon'])

        # 건물 유형 설정
        building_code = building_codes.get(input_data['building'], "00008020104")  # 기본값: 아파트
        for select_name in ['lclsUtilCd', 'mclsUtilCd', 'sclsUtilCd']:
            Select(driver.find_element(By.NAME, select_name)).select_by_value(building_code)

        # 기간 설정
        for key, date_id in zip(['start_date', 'end_date'], ['termStartDt', 'termEndDt']):
            date_field = driver.find_element(By.NAME, date_id)
            date_field.clear()
            date_field.send_keys(input_data[key])

        # 검색 버튼 클릭
        driver.find_element(By.XPATH, '//*[@id="contents"]/form/div[2]/a[1]/img').click()
    except Exception as e:
        st.error(f"검색 조건 설정 중 오류 발생: {e}")
        driver.quit()

# 페이지당 아이템 수 변경
def change_items_per_page(driver):
    try:
        if driver.find_elements(By.ID, 'ipage'):
            Select(driver.find_element(By.ID, 'ipage')).select_by_value("default40")
        else:
            driver.find_element(By.XPATH, '//*[@id="contents"]/div[4]/form[1]/div/div/a[4]/img').click()
    except Exception as e:
        st.error(f"페이지당 아이템 수 변경 중 오류 발생: {e}")
        driver.quit()

# 테이블 데이터 추출
def extract_table_data(driver):
    try:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        table = soup.find('table', attrs={'class': 'Ltbl_list'})
        if not table:
            return pd.DataFrame()
        table_rows = table.find_all('tr')
        row_list = []
        for tr in table_rows:
            td = tr.find_all('td')
            row = [tr.text.strip() for tr in td]
            row_list.append(row)
        return pd.DataFrame(row_list).iloc[1:]
    except Exception as e:
        st.error(f"테이블 데이터 추출 중 오류 발생: {e}")
        return pd.DataFrame()

# 페이지 이동
def navigate_pages(driver, auction_item):
    try:
        page = 1
        while True:
            auction_item = pd.concat([auction_item, extract_table_data(driver)], ignore_index=True)
            page2parent = driver.find_element(By.CLASS_NAME, 'page2')
            children = page2parent.find_elements(By.XPATH, '*')
            if page == 1:
                if len(children) == page:
                    break
                else:
                    children[page].click()
            elif page <= 10:
                if len(children) - 1 == page:
                    break
                else:
                    children[page + 1].click()
            else:
                if len(children) - 2 == (page % 10):
                    break
                else:
                    children[(page % 10) + 2].click()
            page += 1
        driver.find_element(By.XPATH, '//*[@id="contents"]/div[4]/form[1]/div/div/a[4]/img').click()
        return auction_item
    except Exception as e:
        st.error(f"페이지 이동 중 오류 발생: {e}")
        driver.quit()
        return auction_item

# 테이블 데이터 정리
def clean_table_data(auction_item):
    try:
        auction_item = auction_item.iloc[:, 1:]
        col_list = ['사건번호', '물건번호', '소재지', '비고', '감정평가액', '날짜']
        auction_item.columns = col_list
        for col in col_list:
            auction_item[col] = auction_item[col].str.replace('\t', '').apply(lambda x: re.sub(r"\n+", "\n", x))
            auction_item['법원'] = auction_item['사건번호'].str.split('\n').str[1]
            auction_item['사건번호'] = auction_item['사건번호'].str.split('\n').str[2]
            auction_item['용도'] = auction_item['물건번호'].str.split('\n').str[2]
            auction_item['물건번호'] = auction_item['물건번호'].str.split('\n').str[1]
            auction_item['내역'] = auction_item['소재지'].str.split('\n').str[2:].str.join(' ')
            auction_item['소재지'] = auction_item['소재지'].str.split('\n').str[1]
            auction_item['비고'] = auction_item['비고'].str.split('\n').str[1]
            auction_item['최저가격'] = auction_item['감정평가액'].str.split('\n').str[2]
            auction_item['최저비율'] = auction_item['감정평가액'].str.split('\n').str[3].str[1:-1]
            auction_item['감정평가액'] = auction_item['감정평가액'].str.split('\n').str[1]
            auction_item['유찰횟수'] = auction_item['날짜'].str.split('\n').str[3].str.strip()
            auction_item['유찰횟수'] = np.where(auction_item['유찰횟수'].str.len() == 0, '0회', auction_item['유찰횟수'].str.slice(start=2
                    auction_item['유찰횟수'] = np.where(auction_item['유찰횟수'].str.len() == 0, '0회', auction_item['유찰횟수'].str.slice(start=2))
            auction_item['날짜'] = auction_item['날짜'].str.split('\n').str[2]
    
            auction_item = auction_item[['날짜', '법원', '사건번호', '물건번호', '용도', '감정평가액', '최저가격', '최저비율', '유찰횟수', '소재지', '내역', '비고']]
            auction_item = auction_item[~auction_item['비고'].str.contains('지분매각')].reset_index(drop=True)
            return auction_item
        except Exception as e:
            st.error(f"데이터 정리 중 오류 발생: {e}")
            return auction_item
    
    # URL 인코딩
    def encode_to_euc_kr_url(korean_text):
        try:
            euc_kr_encoded = korean_text.encode('euc-kr')
            return urllib.parse.quote(euc_kr_encoded)
        except Exception as e:
            st.error(f"URL 인코딩 오류: {e}")
            return ""
    
    # 각 행에 대해 URL 생성
    def create_url(row):
        try:
            court_name_encoded = encode_to_euc_kr_url(row["법원"])
            sa_year, sa_ser = row["사건번호"].split("타경")
            url = f"https://www.courtauction.go.kr/RetrieveRealEstDetailInqSaList.laf?jiwonNm={court_name_encoded}&saYear={sa_year}&saSer={sa_ser}&_CUR_CMD=InitMulSrch.laf&_SRCH_SRNID=PNO102014&_NEXT_CMD=RetrieveRealEstDetailInqSaList.laf"
            return url
        except Exception as e:
            st.error(f"URL 생성 오류: {e}")
            return ""
    
    # 메인 함수
    def main(input_data, building_codes):
        driver = setup_webdriver()
        if driver:
            navigate_to_search_page(driver)
            set_search_criteria(driver, input_data, building_codes)
            change_items_per_page(driver)
            auction_item = pd.DataFrame()
            auction_item = navigate_pages(driver, auction_item)
            auction_item = clean_table_data(auction_item)
            auction_item["URL"] = auction_item.apply(create_url, axis=1)
            driver.quit()
            return auction_item
        else:
            return pd.DataFrame()
    
    # Streamlit UI 설정
    st.title('법원 경매 검색')
    
    # 입력 폼
    with st.form(key='search_form'):
        jiwon = st.selectbox('지원', [
            '서울중앙지방법원', '서울동부지방법원', '서울서부지방법원'
        ])
        building = st.selectbox('건물 유형', [
            "단독주택", "다가구주택", "다중주택", "아파트", 
            "연립주택", "다세대주택", "기숙사", "빌라", 
            "상가주택", "오피스텔", "주상복합"
        ])
        start_date = st.date_input('시작 날짜', value=datetime.today())
        end_date = st.date_input('종료 날짜', value=datetime.today())
        submit_button = st.form_submit_button(label='검색')
    
    # 검색 버튼 클릭 시
    if submit_button:
        input_data = {
            'jiwon': jiwon,
            'building': building,
            'start_date': start_date.strftime('%Y.%m.%d'),
            'end_date': end_date.strftime('%Y.%m.%d')
        }
    
        building_codes = {
            "단독주택": "00008020101",
            "다가구주택": "00008020102",
            "다중주택": "00008020103",
            "아파트": "00008020104",
            "연립주택": "00008020105",
            "다세대주택": "00008020106",
            "기숙사": "00008020107",
            "빌라": "00008020108",
            "상가주택": "00008020109",
            "오피스텔": "00008020110",
            "주상복합": "00008020111"
        }
    
        # 경매 데이터 수집
        auction_data = main(input_data, building_codes)
        if not auction_data.empty:
            st.dataframe(auction_data)
        else:
            st.warning("검색 결과가 없습니다.")
