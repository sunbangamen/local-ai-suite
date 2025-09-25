# 코딩 예제 모음

## Python 함수 예제

### 기본 함수
```python
def greet(name):
    """사용자에게 인사하는 함수"""
    return f"안녕하세요, {name}님!"

# 사용 예시
message = greet("김철수")
print(message)  # 출력: 안녕하세요, 김철수님!
```

### 파일 처리 함수
```python
def read_file(file_path):
    """파일을 읽어서 내용을 반환하는 함수"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        return "파일을 찾을 수 없습니다."
    except Exception as e:
        return f"오류 발생: {e}"

def write_file(file_path, content):
    """파일에 내용을 쓰는 함수"""
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        return "파일 저장 완료"
    except Exception as e:
        return f"저장 실패: {e}"
```

### 데이터 처리 함수
```python
def process_data(data_list):
    """데이터 리스트를 처리하는 함수"""
    if not data_list:
        return []

    # 중복 제거
    unique_data = list(set(data_list))

    # 정렬
    sorted_data = sorted(unique_data)

    return sorted_data

# 사용 예시
numbers = [3, 1, 4, 1, 5, 9, 2, 6, 5]
result = process_data(numbers)
print(result)  # 출력: [1, 2, 3, 4, 5, 6, 9]
```

## JavaScript 함수 예제

### 비동기 함수
```javascript
async function fetchData(url) {
    try {
        const response = await fetch(url);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('데이터 가져오기 실패:', error);
        return null;
    }
}

// 사용 예시
fetchData('https://api.example.com/data')
    .then(data => console.log(data));
```

### DOM 조작 함수
```javascript
function createElement(tag, className, textContent) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (textContent) element.textContent = textContent;
    return element;
}

function addClickListener(element, callback) {
    element.addEventListener('click', callback);
}
```

## 알고리즘 예제

### 이진 탐색
```python
def binary_search(arr, target):
    """이진 탐색 알고리즘"""
    left, right = 0, len(arr) - 1

    while left <= right:
        mid = (left + right) // 2

        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1  # 찾지 못함
```

### 퀵 정렬
```python
def quicksort(arr):
    """퀵 정렬 알고리즘"""
    if len(arr) <= 1:
        return arr

    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]

    return quicksort(left) + middle + quicksort(right)
```

## 디버깅 팁

### 로그 출력
```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_function(data):
    logger.debug(f"입력 데이터: {data}")

    result = process_data(data)

    logger.debug(f"처리 결과: {result}")
    return result
```

### 예외 처리
```python
def safe_divide(a, b):
    """안전한 나눗셈 함수"""
    try:
        result = a / b
        return result
    except ZeroDivisionError:
        print("0으로 나눌 수 없습니다.")
        return None
    except TypeError:
        print("숫자가 아닌 값입니다.")
        return None
```