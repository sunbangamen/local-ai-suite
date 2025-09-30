#!/usr/bin/env python3
"""
메모리 시스템 테스트 실행 스크립트
다양한 테스트 시나리오를 실행하고 결과를 리포트
"""

import sys
import os
import subprocess
from pathlib import Path

# 프로젝트 루트 디렉토리 설정
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT / 'scripts'))

def run_test_suite(test_name, test_file):
    """개별 테스트 스위트 실행"""
    print(f"\n{'='*60}")
    print(f"🧪 {test_name} 실행 중...")
    print(f"{'='*60}")

    try:
        result = subprocess.run([
            sys.executable, str(test_file)
        ], capture_output=True, text=True, cwd=PROJECT_ROOT)

        print(result.stdout)
        if result.stderr:
            print("❌ 에러 출력:")
            print(result.stderr)

        return result.returncode == 0

    except Exception as e:
        print(f"❌ 테스트 실행 실패: {e}")
        return False

def check_dependencies():
    """테스트 실행에 필요한 의존성 확인"""
    print("🔍 테스트 의존성 확인 중...")

    required_modules = [
        'sqlite3', 'json', 'pathlib',
        'unittest', 'unittest.mock', 'concurrent.futures'
    ]

    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)

    if missing_modules:
        print(f"❌ 누락된 모듈: {missing_modules}")
        return False

    # 메모리 시스템 모듈 확인
    try:
        sys.path.append(str(PROJECT_ROOT / 'scripts'))
        import memory_system
        print("✅ 메모리 시스템 모듈 정상")

        # memory_maintainer는 schedule 의존성 때문에 optional
        try:
            import memory_maintainer
            print("✅ 메모리 유지보수 모듈 정상")
        except ImportError as e:
            print(f"⚠️ 메모리 유지보수 모듈 부분 사용 불가 (schedule 의존성): {e}")

    except ImportError as e:
        print(f"❌ 메모리 시스템 모듈 누락: {e}")
        return False

    print("✅ 모든 의존성 확인 완료")
    return True

def generate_test_report(results):
    """테스트 결과 리포트 생성"""
    print(f"\n{'='*60}")
    print("📊 전체 테스트 결과 리포트")
    print(f"{'='*60}")

    total_tests = len(results)
    passed_tests = sum(1 for success in results.values() if success)
    failed_tests = total_tests - passed_tests

    print(f"총 테스트 스위트: {total_tests}")
    print(f"통과한 테스트: {passed_tests}")
    print(f"실패한 테스트: {failed_tests}")
    print(f"성공률: {(passed_tests/total_tests*100):.1f}%")

    print(f"\n상세 결과:")
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {test_name}")

    if failed_tests == 0:
        print(f"\n🎉 모든 테스트 통과!")
        return True
    else:
        print(f"\n⚠️ {failed_tests}개 테스트 실패")
        return False

def main():
    """메인 테스트 실행 함수"""
    print("🚀 메모리 시스템 테스트 스위트 시작")
    print(f"프로젝트 루트: {PROJECT_ROOT}")

    # 의존성 확인
    if not check_dependencies():
        print("❌ 의존성 확인 실패. 테스트를 중단합니다.")
        return False

    # 테스트 파일 목록
    test_suites = {
        "Qdrant 장애 시나리오": PROJECT_ROOT / "tests" / "memory" / "test_qdrant_failure.py"
    }

    # 테스트 파일 존재 확인
    missing_tests = []
    for name, path in test_suites.items():
        if not path.exists():
            missing_tests.append(f"{name}: {path}")

    if missing_tests:
        print("❌ 누락된 테스트 파일:")
        for missing in missing_tests:
            print(f"   {missing}")
        return False

    # 각 테스트 스위트 실행
    results = {}
    for test_name, test_file in test_suites.items():
        success = run_test_suite(test_name, test_file)
        results[test_name] = success

    # 결과 리포트 생성
    overall_success = generate_test_report(results)

    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)