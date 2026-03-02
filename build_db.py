#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
知识库构建模块
支持文档分类管理
"""

import os
import json
import shutil
from typing import List, Dict
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from config import Config
from embeddings import SiliconFlowEmbeddings
from logger import logger


class DocumentCategory:
    """文档分类常量"""
    REGULATIONS = 'regulations'
    PROCEDURES = 'procedures'
    CAMPUS_LIFE = 'campus_life'
    TEACHING = 'teaching'
    OTHER = 'other'
    
    CATEGORY_NAMES = {
        'regulations': '规章制度',
        'procedures': '办事流程',
        'campus_life': '校园生活',
        'teaching': '教学管理',
        'other': '其他'
    }
    
    CATEGORY_DESCRIPTIONS = {
        'regulations': '校规校纪、管理制度等',
        'procedures': '各类办事指南',
        'campus_life': '宿舍、食堂、图书馆等',
        'teaching': '选课、考试、成绩等',
        'other': '未分类文档'
    }
    
    @classmethod
    def get_all_categories(cls) -> List[Dict]:
        """获取所有分类列表"""
        return [
            {'id': cls.REGULATIONS, 'name': cls.CATEGORY_NAMES[cls.REGULATIONS], 'description': cls.CATEGORY_DESCRIPTIONS[cls.REGULATIONS]},
            {'id': cls.PROCEDURES, 'name': cls.CATEGORY_NAMES[cls.PROCEDURES], 'description': cls.CATEGORY_DESCRIPTIONS[cls.PROCEDURES]},
            {'id': cls.CAMPUS_LIFE, 'name': cls.CATEGORY_NAMES[cls.CAMPUS_LIFE], 'description': cls.CATEGORY_DESCRIPTIONS[cls.CAMPUS_LIFE]},
            {'id': cls.TEACHING, 'name': cls.CATEGORY_NAMES[cls.TEACHING], 'description': cls.CATEGORY_DESCRIPTIONS[cls.TEACHING]},
            {'id': cls.OTHER, 'name': cls.CATEGORY_NAMES[cls.OTHER], 'description': cls.CATEGORY_DESCRIPTIONS[cls.OTHER]},
        ]


class KnowledgeBaseBuilder:
    """知识库构建器"""

    def __init__(self, db_path: str = None):
        """
        初始化知识库构建器

        @param db_path 向量数据库保存路径
        """
        self.db_path = db_path or Config.VECTOR_DB_PATH
        self.metadata_path = os.path.join(os.path.dirname(self.db_path), 'uploads', 'document_metadata.json')

        self.embeddings = SiliconFlowEmbeddings()

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP,
            separators=["\n\n", "\n", "。", "；", " "]
        )

        self._ensure_metadata_file()

        logger.info(f"初始化知识库构建器: db_path={self.db_path}")

    def _ensure_metadata_file(self):
        """确保元数据文件存在"""
        uploads_dir = os.path.dirname(self.metadata_path)
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)
        
        if not os.path.exists(self.metadata_path):
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    def _load_metadata(self) -> Dict:
        """加载文档元数据"""
        try:
            if os.path.exists(self.metadata_path):
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载元数据失败: {e}")
        return {}

    def _save_metadata(self, metadata: Dict):
        """保存文档元数据"""
        try:
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存元数据失败: {e}")

    def load_document(self, file_path: str):
        """
        加载单个文档

        @param file_path 文件路径
        @return 文档对象列表
        """
        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.txt':
            loader = TextLoader(file_path, encoding='utf-8')
        elif ext == '.pdf':
            loader = PyPDFLoader(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {ext}")

        return loader.load()

    def process_documents(self, file_paths: List[str], category: str = None) -> int:
        """
        处理多个文档并添加到向量数据库

        @param file_paths 文件路径列表
        @param category 文档分类
        @return 处理的文档数量
        """
        if category is None:
            category = DocumentCategory.OTHER

        all_chunks = []
        metadata = self._load_metadata()

        for file_path in file_paths:
            logger.info(f"正在处理: {os.path.basename(file_path)}")
            docs = self.load_document(file_path)
            
            for doc in docs:
                doc.metadata['category'] = category
            
            chunks = self.text_splitter.split_documents(docs)
            all_chunks.extend(chunks)
            logger.info(f"分割为 {len(chunks)} 个片段")
            
            doc_name = os.path.basename(file_path)
            metadata[doc_name] = {
                'category': category,
                'chunks': len(chunks)
            }

        if not all_chunks:
            return 0

        if os.path.exists(self.db_path) and os.listdir(self.db_path):
            vector_store = FAISS.load_local(
                self.db_path,
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            vector_store.add_documents(all_chunks)
            logger.info(f"已向现有知识库添加 {len(all_chunks)} 个片段")
        else:
            vector_store = FAISS.from_documents(all_chunks, self.embeddings)
            logger.info(f"已创建新知识库，包含 {len(all_chunks)} 个片段")

        vector_store.save_local(self.db_path)
        logger.info(f"知识库已保存到: {self.db_path}")
        
        self._save_metadata(metadata)

        return len(all_chunks)

    def list_documents(self) -> List[str]:
        """
        获取已处理的文档列表（从向量数据库元数据中提取）

        @return 文档名称列表
        """
        if not os.path.exists(self.db_path) or not os.listdir(self.db_path):
            return []

        try:
            vector_store = FAISS.load_local(
                self.db_path,
                self.embeddings,
                allow_dangerous_deserialization=True
            )

            doc_sources = set()
            docstore = vector_store.docstore
            for doc_id in docstore._dict:
                doc = docstore._dict[doc_id]
                if 'source' in doc.metadata:
                    doc_sources.add(os.path.basename(doc.metadata['source']))

            return sorted(list(doc_sources))
        except Exception as e:
            logger.error(f"获取文档列表失败: {e}")
            return []

    def list_documents_by_category(self) -> Dict:
        """
        获取按分类组织的文档列表

        @return 按分类组织的文档结构
        """
        metadata = self._load_metadata()
        
        categories = DocumentCategory.get_all_categories()
        result = {}
        
        for cat in categories:
            result[cat['id']] = {
                'name': cat['name'],
                'description': cat['description'],
                'documents': [],
                'count': 0
            }
        
        for doc_name, doc_info in metadata.items():
            cat_id = doc_info.get('category', DocumentCategory.OTHER)
            if cat_id not in result:
                cat_id = DocumentCategory.OTHER
            
            result[cat_id]['documents'].append({
                'name': doc_name,
                'chunks': doc_info.get('chunks', 0)
            })
            result[cat_id]['count'] += 1
        
        return result

    def delete_document(self, doc_name: str) -> bool:
        """
        删除指定文档的所有片段（通过重建向量库实现）

        @param doc_name 文档名称
        @return 是否成功
        """
        if not os.path.exists(self.db_path) or not os.listdir(self.db_path):
            return False

        try:
            vector_store = FAISS.load_local(
                self.db_path,
                self.embeddings,
                allow_dangerous_deserialization=True
            )

            docstore = vector_store.docstore
            all_docs = []
            docs_to_delete = []

            for doc_id in list(docstore._dict.keys()):
                doc = docstore._dict[doc_id]
                source = doc.metadata.get('source', '')
                if os.path.basename(source) == doc_name:
                    docs_to_delete.append(doc_id)
                else:
                    all_docs.append(doc)

            if not docs_to_delete:
                return False

            if all_docs:
                new_vector_store = FAISS.from_documents(all_docs, self.embeddings)
                new_vector_store.save_local(self.db_path)
                logger.info(f"已删除文档 '{doc_name}'，剩余 {len(all_docs)} 个片段")
            else:
                shutil.rmtree(self.db_path)
                os.makedirs(self.db_path)
                logger.info(f"已删除最后一个文档 '{doc_name}'，知识库已清空")
            
            metadata = self._load_metadata()
            if doc_name in metadata:
                del metadata[doc_name]
                self._save_metadata(metadata)

            return True
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False

    def clear_all(self):
        """清空整个知识库"""
        if os.path.exists(self.db_path):
            shutil.rmtree(self.db_path)
            os.makedirs(self.db_path)
            logger.info("知识库已清空")
        
        self._save_metadata({})
