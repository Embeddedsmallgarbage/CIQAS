#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SiliconFlow Embedding 类
支持 BAAI/bge-m3 等嵌入模型
"""

import requests
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_core.embeddings import Embeddings

from config import Config
from logger import logger


class SiliconFlowEmbeddings(Embeddings):
    """SiliconFlow Embedding 客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: int = 20,
        max_workers: int = 4
    ):
        """
        初始化 SiliconFlow Embedding 客户端

        @param api_key SiliconFlow API Key
        @param base_url API 基础 URL
        @param model 嵌入模型名称
        @param batch_size 批量处理大小
        @param max_workers 并发工作线程数
        """
        self.api_key = api_key or Config.SILICONFLOW_API_KEY
        self.base_url = base_url or Config.SILICONFLOW_BASE_URL
        self.model = model or Config.SILICONFLOW_EMBEDDING_MODEL
        self.api_url = f"{self.base_url}/embeddings"
        self.batch_size = batch_size
        self.max_workers = max_workers

        if not self.api_key:
            raise ValueError("SILICONFLOW_API_KEY 未配置，请在 .env 文件中设置")

        logger.info(f"初始化 SiliconFlow Embedding: model={self.model}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        嵌入多个文档（支持批量处理）

        @param texts 文本列表
        @return 嵌入向量列表
        """
        if not texts:
            return []

        all_embeddings = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]

            try:
                batch_embeddings = self._embed_batch(batch)
                all_embeddings.extend(batch_embeddings)
                logger.debug(f"已处理 {min(i + self.batch_size, len(texts))}/{len(texts)} 个文本")
            except Exception as e:
                logger.warning(f"批量处理失败，切换到单条处理: {e}")
                for text in batch:
                    embedding = self._get_embedding(text)
                    all_embeddings.append(embedding)

        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """
        嵌入单个查询

        @param text 查询文本
        @return 嵌入向量
        """
        return self._get_embedding(text)

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量获取嵌入向量

        @param texts 文本列表
        @return 嵌入向量列表
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        data = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float"
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()

            if "data" in result:
                sorted_data = sorted(result["data"], key=lambda x: x.get("index", 0))
                return [item["embedding"] for item in sorted_data]
            else:
                raise ValueError(f"API 返回格式错误: {result}")

        except requests.exceptions.Timeout:
            logger.error("SiliconFlow API 请求超时")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"SiliconFlow API 请求失败: {e}")
            raise

    def _get_embedding(self, text: str) -> List[float]:
        """
        获取单个文本的嵌入向量

        @param text 输入文本
        @return 嵌入向量
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        data = {
            "model": self.model,
            "input": text,
            "encoding_format": "float"
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if "data" in result and len(result["data"]) > 0:
                return result["data"][0]["embedding"]
            else:
                raise ValueError(f"API 返回格式错误: {result}")

        except requests.exceptions.Timeout:
            logger.error("SiliconFlow API 请求超时")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"SiliconFlow API 请求失败: {e}")
            raise


def get_embeddings() -> SiliconFlowEmbeddings:
    """
    获取 Embedding 实例

    @return Embedding 实例
    """
    return SiliconFlowEmbeddings()
