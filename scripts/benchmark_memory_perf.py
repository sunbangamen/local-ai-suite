#!/usr/bin/env python3
"""
Memory System Performance Benchmark
메모리 시스템 성능 검증 - 100만개 대화 저장/검색 벤치마크
"""

import sys
import time
import asyncio
from pathlib import Path
from datetime import datetime
import random
import json

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from memory_system import MemorySystem


class MemoryBenchmark:
    def __init__(self, test_size: int = 1000):
        """
        Args:
            test_size: 테스트할 대화 개수 (기본 1000, 실제 100만 테스트는 시간 소요)
        """
        self.test_size = test_size
        self.memory = MemorySystem(data_dir="/tmp/benchmark-memory")
        self.project_id = None
        self.results = {}

    def setup(self):
        """벤치마크 환경 설정"""
        print("=" * 80)
        print(f"Memory System Performance Benchmark - {self.test_size:,} conversations")
        print("=" * 80)

        self.project_id = self.memory.get_project_id("/tmp/benchmark-project")
        print(f"✅ Benchmark project: {self.project_id}\n")

    def generate_test_conversation(self, index: int) -> tuple:
        """테스트용 대화 생성"""
        queries = [
            f"Python에서 파일 읽는 방법 {index}",
            f"Django REST API 설계 패턴 {index}",
            f"React Hook 사용법 {index}",
            f"SQL 쿼리 최적화 방법 {index}",
            f"Docker 컨테이너 관리 {index}",
        ]

        responses = [
            f"Python에서는 open() 함수를 사용하여 파일을 읽을 수 있습니다. 예제: with open('file.txt', 'r') as f: data = f.read() #{index}",
            f"Django REST Framework에서는 ViewSet과 Serializer를 사용하여 API를 설계할 수 있습니다. #{index}",
            f"React Hook은 useState와 useEffect를 주로 사용합니다. 예제: const [state, setState] = useState(null) #{index}",
            f"SQL 쿼리 최적화는 인덱스 추가, 쿼리 구조 개선, EXPLAIN 분석 등을 통해 가능합니다. #{index}",
            f"Docker 컨테이너는 docker ps, docker logs, docker exec 등의 명령어로 관리할 수 있습니다. #{index}",
        ]

        models = ["chat-7b", "code-7b"]

        query = random.choice(queries)
        response = random.choice(responses)
        model = random.choice(models)

        return query, response, model

    def benchmark_save(self):
        """대화 저장 성능 벤치마크"""
        print(f"[Benchmark 1] 대화 저장 성능 ({self.test_size:,}개)")
        print("-" * 80)

        conversation_ids = []
        start_time = time.time()

        for i in range(self.test_size):
            query, response, model = self.generate_test_conversation(i)

            conv_id = self.memory.save_conversation(
                project_id=self.project_id,
                user_query=query,
                ai_response=response,
                model_used=model,
                session_id=f"benchmark-session-{i // 100}",
            )

            if conv_id:
                conversation_ids.append(conv_id)

            # Progress indicator
            if (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                print(
                    f"  진행: {i + 1:,}/{self.test_size:,} ({rate:.1f} conversations/sec)",
                    end="\r",
                )

        elapsed_time = time.time() - start_time
        avg_time_per_conv = (elapsed_time / self.test_size) * 1000  # ms

        print(f"\n✅ 저장 완료:")
        print(f"   총 시간: {elapsed_time:.2f}초")
        print(f"   평균 저장 시간: {avg_time_per_conv:.2f}ms/conversation")
        print(f"   처리량: {self.test_size / elapsed_time:.1f} conversations/sec")

        self.results["save"] = {
            "total_conversations": len(conversation_ids),
            "elapsed_time_sec": elapsed_time,
            "avg_time_ms": avg_time_per_conv,
            "throughput_per_sec": self.test_size / elapsed_time,
        }

        return conversation_ids

    def benchmark_fts_search(self, num_queries: int = 100):
        """FTS5 검색 성능 벤치마크"""
        print(f"\n[Benchmark 2] FTS5 검색 성능 ({num_queries}개 쿼리)")
        print("-" * 80)

        test_queries = [
            "Python 파일",
            "Django API",
            "React Hook",
            "SQL 쿼리",
            "Docker 컨테이너",
        ]

        search_times = []
        total_results = 0

        for i in range(num_queries):
            query = random.choice(test_queries)

            start_time = time.time()
            results = self.memory.search_conversations(
                project_id=self.project_id, query=query, limit=10
            )
            elapsed_ms = (time.time() - start_time) * 1000

            search_times.append(elapsed_ms)
            total_results += len(results)

            if (i + 1) % 20 == 0:
                print(f"  진행: {i + 1}/{num_queries}", end="\r")

        avg_time = sum(search_times) / len(search_times)
        p95_time = sorted(search_times)[int(len(search_times) * 0.95)]
        p99_time = sorted(search_times)[int(len(search_times) * 0.99)]

        print(f"\n✅ 검색 완료:")
        print(f"   평균 검색 시간: {avg_time:.2f}ms")
        print(f"   P95 검색 시간: {p95_time:.2f}ms")
        print(f"   P99 검색 시간: {p99_time:.2f}ms")
        print(f"   평균 결과 수: {total_results / num_queries:.1f}개")
        print(
            f"   목표 달성 여부: {'✅ PASS' if p95_time < 1000 else '❌ FAIL'} (목표: < 1000ms)"
        )

        self.results["fts_search"] = {
            "num_queries": num_queries,
            "avg_time_ms": avg_time,
            "p95_time_ms": p95_time,
            "p99_time_ms": p99_time,
            "avg_results": total_results / num_queries,
            "target_met": p95_time < 1000,
        }

    async def benchmark_vector_search(self, num_queries: int = 50):
        """벡터 검색 성능 벤치마크"""
        print(f"\n[Benchmark 3] 벡터 검색 성능 ({num_queries}개 쿼리)")
        print("-" * 80)

        if not self.memory._vector_enabled:
            print("⚠️ 벡터 검색이 비활성화되어 있습니다. 스킵합니다.")
            self.results["vector_search"] = {"skipped": True}
            return

        # 먼저 임베딩 생성
        print("  임베딩 생성 중...")
        start_embed = time.time()
        processed = await self.memory.process_pending_embeddings(
            self.project_id, batch_size=64
        )
        embed_time = time.time() - start_embed
        print(f"  ✅ {processed}개 임베딩 생성 완료 ({embed_time:.2f}초)")

        # 벡터 검색 테스트
        test_queries = [
            "파일 입출력 처리 방법",
            "웹 API 설계 및 구현",
            "프론트엔드 상태 관리",
            "데이터베이스 쿼리 최적화",
            "컨테이너 오케스트레이션",
        ]

        search_times = []
        total_results = 0

        for i in range(num_queries):
            query = random.choice(test_queries)

            start_time = time.time()
            results = await self.memory.vector_search_conversations(
                project_id=self.project_id, query=query, limit=10, score_threshold=0.5
            )
            elapsed_ms = (time.time() - start_time) * 1000

            search_times.append(elapsed_ms)
            total_results += len(results)

            if (i + 1) % 10 == 0:
                print(f"  진행: {i + 1}/{num_queries}", end="\r")

        avg_time = sum(search_times) / len(search_times)
        p95_time = sorted(search_times)[int(len(search_times) * 0.95)]

        print(f"\n✅ 벡터 검색 완료:")
        print(f"   임베딩 생성: {embed_time:.2f}초 ({processed}개)")
        print(f"   평균 검색 시간: {avg_time:.2f}ms")
        print(f"   P95 검색 시간: {p95_time:.2f}ms")
        print(f"   평균 결과 수: {total_results / num_queries:.1f}개")

        self.results["vector_search"] = {
            "num_queries": num_queries,
            "embeddings_generated": processed,
            "embedding_time_sec": embed_time,
            "avg_search_time_ms": avg_time,
            "p95_search_time_ms": p95_time,
            "avg_results": total_results / num_queries,
        }

    async def benchmark_hybrid_search(self, num_queries: int = 50):
        """하이브리드 검색 성능 벤치마크"""
        print(f"\n[Benchmark 4] 하이브리드 검색 성능 ({num_queries}개 쿼리)")
        print("-" * 80)

        if not self.memory._vector_enabled:
            print("⚠️ 벡터 검색이 비활성화되어 있습니다. 스킵합니다.")
            self.results["hybrid_search"] = {"skipped": True}
            return

        test_queries = [
            "Python 프로그래밍",
            "웹 개발",
            "데이터베이스",
            "클라우드 인프라",
            "DevOps 자동화",
        ]

        search_times = []
        total_results = 0

        for i in range(num_queries):
            query = random.choice(test_queries)

            start_time = time.time()
            results = await self.memory.hybrid_search_conversations(
                project_id=self.project_id, query=query, limit=10
            )
            elapsed_ms = (time.time() - start_time) * 1000

            search_times.append(elapsed_ms)
            total_results += len(results)

            if (i + 1) % 10 == 0:
                print(f"  진행: {i + 1}/{num_queries}", end="\r")

        avg_time = sum(search_times) / len(search_times)
        p95_time = sorted(search_times)[int(len(search_times) * 0.95)]

        print(f"\n✅ 하이브리드 검색 완료:")
        print(f"   평균 검색 시간: {avg_time:.2f}ms")
        print(f"   P95 검색 시간: {p95_time:.2f}ms")
        print(f"   평균 결과 수: {total_results / num_queries:.1f}개")

        self.results["hybrid_search"] = {
            "num_queries": num_queries,
            "avg_time_ms": avg_time,
            "p95_time_ms": p95_time,
            "avg_results": total_results / num_queries,
        }

    def benchmark_stats(self):
        """통계 조회 성능 벤치마크"""
        print(f"\n[Benchmark 5] 통계 조회 성능")
        print("-" * 80)

        start_time = time.time()
        stats = self.memory.get_conversation_stats(self.project_id)
        elapsed_ms = (time.time() - start_time) * 1000

        print(f"✅ 통계 조회 완료: {elapsed_ms:.2f}ms")
        print(f"   총 대화: {stats['total_conversations']:,}개")
        print(f"   평균 중요도: {stats['avg_importance']:.2f}/10")

        self.results["stats"] = {
            "query_time_ms": elapsed_ms,
            "total_conversations": stats["total_conversations"],
        }

    def save_results(self):
        """벤치마크 결과 저장"""
        output_file = (
            Path("/tmp")
            / f"memory_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print(f"\n💾 벤치마크 결과 저장: {output_file}")

    def print_summary(self):
        """벤치마크 요약 출력"""
        print("\n" + "=" * 80)
        print("Benchmark Summary")
        print("=" * 80)

        # 저장 성능
        if "save" in self.results:
            save = self.results["save"]
            print(f"\n📝 저장 성능:")
            print(f"   처리량: {save['throughput_per_sec']:.1f} conversations/sec")
            print(f"   평균 시간: {save['avg_time_ms']:.2f}ms")
            print(
                f"   목표 달성: {'✅ PASS' if save['avg_time_ms'] < 100 else '⚠️  SLOW'} (목표: < 100ms)"
            )

        # FTS5 검색
        if "fts_search" in self.results:
            fts = self.results["fts_search"]
            print(f"\n🔍 FTS5 검색 성능:")
            print(f"   평균: {fts['avg_time_ms']:.2f}ms")
            print(f"   P95: {fts['p95_time_ms']:.2f}ms")
            print(
                f"   목표 달성: {'✅ PASS' if fts['target_met'] else '❌ FAIL'} (목표: < 1000ms)"
            )

        # 벡터 검색
        if "vector_search" in self.results and not self.results["vector_search"].get(
            "skipped"
        ):
            vec = self.results["vector_search"]
            print(f"\n🧠 벡터 검색 성능:")
            print(f"   평균: {vec['avg_search_time_ms']:.2f}ms")
            print(f"   P95: {vec['p95_search_time_ms']:.2f}ms")

        # 하이브리드 검색
        if "hybrid_search" in self.results and not self.results["hybrid_search"].get(
            "skipped"
        ):
            hyb = self.results["hybrid_search"]
            print(f"\n🔀 하이브리드 검색 성능:")
            print(f"   평균: {hyb['avg_time_ms']:.2f}ms")
            print(f"   P95: {hyb['p95_time_ms']:.2f}ms")

        print("\n" + "=" * 80)


async def main():
    """메인 벤치마크 실행"""
    import argparse

    parser = argparse.ArgumentParser(description="Memory System Performance Benchmark")
    parser.add_argument(
        "--size",
        type=int,
        default=1000,
        help="Number of conversations to test (default: 1000)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full 1M conversation test (takes ~1 hour)",
    )
    args = parser.parse_args()

    test_size = 1_000_000 if args.full else args.size

    if args.full:
        print("⚠️  Full 1M conversation test will take approximately 1 hour")
        response = input("Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Cancelled.")
            return 1

    benchmark = MemoryBenchmark(test_size=test_size)

    try:
        # Setup
        benchmark.setup()

        # Run benchmarks
        benchmark.benchmark_save()
        benchmark.benchmark_fts_search(num_queries=100)
        await benchmark.benchmark_vector_search(num_queries=50)
        await benchmark.benchmark_hybrid_search(num_queries=50)
        benchmark.benchmark_stats()

        # Results
        benchmark.save_results()
        benchmark.print_summary()

        print("\n✅ 모든 벤치마크 완료!")
        return 0

    except Exception as e:
        print(f"\n❌ 벤치마크 실패: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
