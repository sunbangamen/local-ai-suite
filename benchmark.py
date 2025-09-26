#!/usr/bin/env python3
"""
MCP Security 성능 벤치마크 측정 스크립트
"""

import time
import sys
import os
import statistics
from pathlib import Path

# 테스트를 위한 상대 임포트 설정
sys.path.append(os.path.join(os.path.dirname(__file__), 'services', 'mcp-server'))

from security import SecurityValidator, SecureExecutionEnvironment
from safe_api import SecurePathValidator, SafeFileAPI


class PerformanceBenchmark:
    """성능 벤치마크 측정기"""

    def __init__(self):
        self.validator = SecurityValidator("normal")
        self.strict_validator = SecurityValidator("strict")
        self.executor = SecureExecutionEnvironment(self.validator)
        self.path_validator = SecurePathValidator()
        self.file_api = SafeFileAPI()

    def time_function(self, func, *args, **kwargs):
        """함수 실행 시간 측정"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        return end_time - start_time, result

    def benchmark_ast_validation(self, iterations=100):
        """AST 검증 성능 벤치마크"""
        print("🔍 AST 보안 검증 성능 테스트...")

        test_codes = [
            "import pathlib; print('safe')",
            "import json; data = {'key': 'value'}",
            "import math; result = math.sqrt(16)",
            "import os; print(os.getcwd())",
            "import sys; print(sys.version)"
        ]

        times = []
        for _ in range(iterations):
            start_time = time.time()
            for code in test_codes:
                self.validator.validate_code(code)
            end_time = time.time()
            times.append(end_time - start_time)

        avg_time = statistics.mean(times)
        total_validations = len(test_codes) * iterations
        validations_per_sec = total_validations / sum(times)

        print(f"  평균 시간: {avg_time*1000:.2f}ms ({iterations}회 반복)")
        print(f"  초당 검증: {validations_per_sec:.1f} validations/sec")
        print(f"  검증당 평균: {(sum(times)/total_validations)*1000:.2f}ms")

        return avg_time

    def benchmark_path_validation(self, iterations=100):
        """경로 검증 성능 벤치마크"""
        print("🛤️  경로 보안 검증 성능 테스트...")

        test_paths = [
            "test.txt",
            "./documents/readme.md",
            "data/config.json",
            "../safe/path.txt",
            "subdir/nested/file.py"
        ]

        times = []
        for _ in range(iterations):
            start_time = time.time()
            for path in test_paths:
                try:
                    self.path_validator.validate_and_resolve_path(path)
                except Exception:
                    # 경로가 존재하지 않을 수 있지만 성능 측정에는 영향 없음
                    pass
            end_time = time.time()
            times.append(end_time - start_time)

        avg_time = statistics.mean(times)
        total_validations = len(test_paths) * iterations
        validations_per_sec = total_validations / sum(times)

        print(f"  평균 시간: {avg_time*1000:.2f}ms ({iterations}회 반복)")
        print(f"  초당 검증: {validations_per_sec:.1f} validations/sec")
        print(f"  검증당 평균: {(sum(times)/total_validations)*1000:.2f}ms")

        return avg_time

    def benchmark_code_execution(self, iterations=10):
        """코드 실행 성능 벤치마크"""
        print("⚡ 코드 실행 성능 테스트...")

        test_codes = [
            "print('Hello World')",
            "import json; print(json.dumps({'key': 'value'}))",
            "import math; print(math.sqrt(16))",
            "import os; print(f'Current dir: {os.getcwd()}')"
        ]

        times = []
        for code in test_codes:
            code_times = []
            for _ in range(iterations):
                start_time = time.time()
                result = self.executor.execute_python_code(code)
                end_time = time.time()
                if result["success"]:
                    code_times.append(end_time - start_time)

            if code_times:
                avg_time = statistics.mean(code_times)
                times.append(avg_time)
                print(f"  코드: {code[:30]}... => {avg_time*1000:.0f}ms")

        if times:
            overall_avg = statistics.mean(times)
            print(f"  전체 평균: {overall_avg*1000:.0f}ms")
            return overall_avg

        return 0

    def benchmark_memory_usage(self):
        """메모리 사용량 측정"""
        print("💾 메모리 사용량 측정...")

        try:
            import psutil
            process = psutil.Process()

            # 초기 메모리 사용량
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            # 대량 검증 수행
            for _ in range(1000):
                self.validator.validate_code("import pathlib; print('test')")

            # 최종 메모리 사용량
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            print(f"  초기 메모리: {initial_memory:.1f} MB")
            print(f"  최종 메모리: {final_memory:.1f} MB")
            print(f"  메모리 증가: {memory_increase:.1f} MB")

            return memory_increase

        except ImportError:
            print("  psutil이 설치되지 않아 메모리 측정을 건너뜁니다.")
            return 0

    def run_all_benchmarks(self):
        """모든 벤치마크 실행"""
        print("🚀 MCP Security 성능 벤치마크 시작...")
        print("=" * 50)

        # AST 검증 성능
        ast_time = self.benchmark_ast_validation()
        print()

        # 경로 검증 성능
        path_time = self.benchmark_path_validation()
        print()

        # 코드 실행 성능
        exec_time = self.benchmark_code_execution()
        print()

        # 메모리 사용량
        memory_increase = self.benchmark_memory_usage()
        print()

        # 결과 요약
        print("📊 성능 벤치마크 결과 요약")
        print("=" * 50)
        print(f"AST 검증 평균 시간: {ast_time*1000:.2f}ms")
        print(f"경로 검증 평균 시간: {path_time*1000:.2f}ms")
        if exec_time > 0:
            print(f"코드 실행 평균 시간: {exec_time*1000:.0f}ms")
        if memory_increase > 0:
            print(f"메모리 증가량: {memory_increase:.1f} MB")

        # 성능 등급 평가
        print("\n🎯 성능 평가")
        print("=" * 50)

        if ast_time < 0.001:  # 1ms 미만
            print("✅ AST 검증: 우수 (< 1ms)")
        elif ast_time < 0.005:  # 5ms 미만
            print("⚠️  AST 검증: 양호 (< 5ms)")
        else:
            print("❌ AST 검증: 개선 필요 (> 5ms)")

        if path_time < 0.001:  # 1ms 미만
            print("✅ 경로 검증: 우수 (< 1ms)")
        elif path_time < 0.005:  # 5ms 미만
            print("⚠️  경로 검증: 양호 (< 5ms)")
        else:
            print("❌ 경로 검증: 개선 필요 (> 5ms)")

        if exec_time > 0:
            if exec_time < 0.1:  # 100ms 미만
                print("✅ 코드 실행: 우수 (< 100ms)")
            elif exec_time < 0.5:  # 500ms 미만
                print("⚠️  코드 실행: 양호 (< 500ms)")
            else:
                print("❌ 코드 실행: 개선 필요 (> 500ms)")

        if memory_increase >= 0:
            if memory_increase < 10:  # 10MB 미만
                print("✅ 메모리 사용: 우수 (< 10MB 증가)")
            elif memory_increase < 50:  # 50MB 미만
                print("⚠️  메모리 사용: 양호 (< 50MB 증가)")
            else:
                print("❌ 메모리 사용: 개선 필요 (> 50MB 증가)")

        print("\n🏁 벤치마크 완료!")


if __name__ == "__main__":
    benchmark = PerformanceBenchmark()
    benchmark.run_all_benchmarks()