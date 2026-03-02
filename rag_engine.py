#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
RAG 问答引擎核心模块
支持动态参数配置
"""

import os
from typing import List, Tuple, Generator
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_deepseek import ChatDeepSeek

from config import Config
from embeddings import SiliconFlowEmbeddings
from logger import logger


class QASystem:
    """RAG 问答系统"""

    def __init__(self, db_path: str = None):
        """
        初始化问答系统

        @param db_path 向量数据库路径
        """
        self.db_path = db_path or Config.VECTOR_DB_PATH
        self.vector_store = None
        self.llm = None
        self.prompt_template = None

        self.embeddings = SiliconFlowEmbeddings()

        self._init_llm()
        self._init_prompt()
        self._load_vector_store()

        logger.info(f"初始化问答系统: db_path={self.db_path}")

    def _init_llm(self):
        """初始化 LLM（使用动态参数）"""
        if not Config.DEEPSEEK_API_KEY:
            logger.warning("DEEPSEEK_API_KEY 未设置，LLM 功能将不可用")
            return

        # 获取动态参数
        llm_settings = Config.get_llm_settings()

        self.llm = ChatDeepSeek(
            model=Config.DEEPSEEK_MODEL,
            api_key=Config.DEEPSEEK_API_KEY,
            temperature=llm_settings['temperature'],
            max_tokens=llm_settings['max_tokens'],
            top_p=llm_settings['top_p'],
            frequency_penalty=llm_settings['frequency_penalty'],
            presence_penalty=llm_settings['presence_penalty'],
            streaming=True
        )
        logger.info(
            f"初始化 LLM: model={Config.DEEPSEEK_MODEL}, "
            f"temperature={llm_settings['temperature']}, "
            f"max_tokens={llm_settings['max_tokens']}, "
            f"top_p={llm_settings['top_p']}"
        )

    def reload_settings(self):
        """
        重新加载设置（用于参数更新后）

        重新初始化 LLM 以应用新的参数设置
        """
        logger.info("重新加载问答系统设置...")

        try:
            # 重新初始化 LLM
            self._init_llm()
            logger.info("问答系统设置重新加载完成")
        except Exception as e:
            logger.error(f"重新加载设置失败: {e}")
            raise

    def _init_prompt(self):
        """初始化 Prompt 模板"""
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的高校事务咨询助手，专门回答关于学校规章制度、办事流程、校园生活等问题。

请遵循以下规则：
1. 主要基于提供的参考资料回答问题
2. 可以进行合理的推理和联想，将相关内容关联起来（如"奖项"和"荣誉"）
3. 如果参考资料中确实没有相关信息，请明确告知用户"根据现有资料无法回答"
4. 回答要简洁明了，分点说明
5. 涉及具体流程时，请列出步骤
6. 使用中文回答

参考资料：
{context}"""),
            ("human", "{question}")
        ])

    def _load_vector_store(self):
        """加载或初始化向量数据库"""
        if os.path.exists(self.db_path) and os.listdir(self.db_path):
            try:
                self.vector_store = FAISS.load_local(
                    self.db_path,
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info(f"已加载向量数据库: {self.db_path}")
            except Exception as e:
                logger.error(f"加载向量数据库失败: {e}")
                self.vector_store = None
        else:
            logger.warning(f"向量数据库不存在: {self.db_path}")
            self.vector_store = None

    def is_db_ready(self) -> bool:
        """检查向量数据库是否就绪"""
        return self.vector_store is not None

    def reload_vector_store(self):
        """重新加载向量数据库（用于更新后）"""
        self._load_vector_store()

    def get_answer(self, question: str) -> Tuple[str, List[Document]]:
        """
        获取问题答案

        @param question 用户问题
        @return (答案, 相关文档列表)
        """
        if not self.vector_store:
            return "知识库尚未初始化，请先上传文档。", []

        if not self.llm:
            return "LLM 未配置，请检查 DEEPSEEK_API_KEY 设置。", []

        # 获取动态检索参数
        retrieval_k = Config.get_setting('embedding_retrieval_k', Config.RETRIEVAL_K)

        retriever = self.vector_store.as_retriever(
            search_kwargs={"k": retrieval_k}
        )
        relevant_docs = retriever.invoke(question)

        if not relevant_docs:
            return "抱歉，在知识库中没有找到相关资料。", []

        context = "\n\n".join([
            f"[文档 {i+1}] {doc.page_content}"
            for i, doc in enumerate(relevant_docs)
        ])

        messages = self.prompt_template.format_messages(
            context=context,
            question=question
        )

        response = self.llm.invoke(messages)
        answer = response.content

        logger.info(f"问答完成: question={question[:50]}...")

        return answer, relevant_docs

    def get_answer_stream(
        self,
        question: str
    ) -> Generator[Tuple[str, List[Document]], None, None]:
        """
        流式获取问题答案

        @param question 用户问题
        @return 生成器，每次 yield (答案片段, 相关文档列表)
        """
        if not self.vector_store:
            yield "知识库尚未初始化，请先上传文档。", []
            return

        if not self.llm:
            yield "LLM 未配置，请检查 DEEPSEEK_API_KEY 设置。", []
            return

        # 获取动态检索参数
        retrieval_k = Config.get_setting('embedding_retrieval_k', Config.RETRIEVAL_K)

        retriever = self.vector_store.as_retriever(
            search_kwargs={"k": retrieval_k}
        )
        relevant_docs = retriever.invoke(question)

        if not relevant_docs:
            yield "抱歉，在知识库中没有找到相关资料。", []
            return

        context = "\n\n".join([
            f"[文档 {i+1}] {doc.page_content}"
            for i, doc in enumerate(relevant_docs)
        ])

        messages = self.prompt_template.format_messages(
            context=context,
            question=question
        )

        full_answer = ""
        repetition_count = 0
        max_repetition = 3  # 允许的最大重复次数

        for chunk in self.llm.stream(messages):
            if chunk.content:
                content = chunk.content
                full_answer += content

                # 检测重复内容
                if len(full_answer) > 100:
                    # 检查最后 50 个字符是否在之前出现过
                    last_50 = full_answer[-50:]
                    previous_text = full_answer[:-50]
                    if last_50 in previous_text:
                        repetition_count += 1
                        logger.warning(f"检测到重复内容，重复次数: {repetition_count}")

                        if repetition_count >= max_repetition:
                            logger.error("模型陷入重复循环，强制终止生成")
                            yield "\n\n[回答被截断：检测到重复输出]", relevant_docs
                            break

                yield content, relevant_docs

        logger.info(f"流式问答完成: question={question[:50]}..., length={len(full_answer)}")

    def get_relevant_docs(self, question: str) -> List[Document]:
        """
        仅获取相关文档（不生成答案）

        @param question 用户问题
        @return 相关文档列表
        """
        if not self.vector_store:
            return []

        # 获取动态检索参数
        retrieval_k = Config.get_setting('embedding_retrieval_k', Config.RETRIEVAL_K)

        retriever = self.vector_store.as_retriever(
            search_kwargs={"k": retrieval_k}
        )
        return retriever.invoke(question)
