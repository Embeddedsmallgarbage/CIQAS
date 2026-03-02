#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Flask 后端主程序
"""

import os
import re
import json
import secrets
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for, flash, session
from werkzeug.utils import secure_filename

from config import Config
from logger import logger
from database import db
from rag_engine import QASystem
from build_db import KnowledgeBaseBuilder
from auth import AuthManager, user_manager, login_required, admin_required


def safe_filename(filename: str) -> str:
    """
    安全文件名处理，支持中文
    
    @param filename 原始文件名
    @return 安全的文件名
    """
    filename = re.sub(r'[/\\]', '_', filename)
    filename = re.sub(r'[<>:"|?*]', '', filename)
    filename = filename.strip()
    if not filename:
        filename = 'unnamed_file'
    return filename


Config.ensure_directories()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

qa_system = QASystem()
kb_builder = KnowledgeBaseBuilder()


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    登录页面
    
    @return 登录页面或重定向
    """
    if AuthManager.is_logged_in():
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('请输入账号和密码', 'error')
            return render_template('login.html')
        
        user = user_manager.verify_user(username, password)
        
        if user:
            AuthManager.login(user)
            return redirect(url_for('index'))
        else:
            flash('账号或密码错误', 'error')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """
    登出
    
    @return 重定向到登录页
    """
    AuthManager.logout()
    return redirect(url_for('login'))


@app.route('/api/user/info')
@login_required
def user_info():
    """
    获取当前用户信息
    
    @return 用户信息 JSON
    """
    user = AuthManager.get_current_user()
    if user:
        return jsonify({
            'logged_in': True,
            'user': user.to_dict()
        })
    return jsonify({'logged_in': False, 'user': None})


@app.route('/')
@login_required
def index():
    """主页面"""
    user = AuthManager.get_current_user()
    return render_template('index.html', user=user)


@app.route('/health')
def health():
    """健康检查端点"""
    return jsonify({
        'status': 'healthy',
        'kb_ready': qa_system.is_db_ready(),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    """处理聊天请求"""
    data = request.json
    question = data.get('question', '')
    conversation_id = data.get('conversation_id')
    stream = data.get('stream', False)

    if not question:
        return jsonify({'error': '问题不能为空'}), 400

    if not conversation_id:
        conversation = db.get_conversation(conversation_id)
        if not conversation:
            conversation_id = db.create_conversation()
    else:
        conversation = db.get_conversation(conversation_id)
        if not conversation:
            conversation_id = db.create_conversation()

    db.add_message(conversation_id, 'user', question)

    user_messages = db.get_conversation(conversation_id).get('messages', [])
    user_msg_count = sum(1 for m in user_messages if m['role'] == 'user')
    if user_msg_count == 1:
        title = question[:20] + '...' if len(question) > 20 else question
        db.update_conversation_title(conversation_id, title)

    if stream:
        return Response(
            stream_with_context(generate_stream_response(question, conversation_id)),
            mimetype='text/event-stream'
        )

    answer, source_docs = qa_system.get_answer(question)

    db.add_message(conversation_id, 'assistant', answer)

    sources = format_sources(source_docs)

    logger.info(f"问答完成: conversation={conversation_id}")

    return jsonify({
        'answer': answer,
        'sources': sources,
        'conversation_id': conversation_id
    })


def generate_stream_response(question: str, conversation_id: str):
    """生成流式响应"""
    full_answer = ""
    sources = []

    try:
        for chunk, docs in qa_system.get_answer_stream(question):
            full_answer += chunk
            if not sources and docs:
                sources = format_sources(docs)

            data = json.dumps({
                'type': 'chunk',
                'content': chunk
            }, ensure_ascii=False)
            yield f"data: {data}\n\n"

        db.add_message(conversation_id, 'assistant', full_answer)

        done_data = json.dumps({
            'type': 'done',
            'sources': sources,
            'conversation_id': conversation_id
        }, ensure_ascii=False)
        yield f"data: {done_data}\n\n"

        logger.info(f"流式问答完成: conversation={conversation_id}")

    except Exception as e:
        logger.error(f"流式响应错误: {e}")
        error_data = json.dumps({
            'type': 'error',
            'message': str(e)
        }, ensure_ascii=False)
        yield f"data: {error_data}\n\n"


def format_sources(source_docs) -> list:
    """格式化来源文档"""
    sources = []
    for doc in source_docs:
        sources.append({
            'source': doc.metadata.get('source', '未知文件'),
            'content': doc.page_content[:200] + '...' if len(doc.page_content) > 200 else doc.page_content
        })
    return sources


@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    """获取所有对话列表"""
    conv_list = db.list_conversations()
    return jsonify(conv_list)


@app.route('/api/conversations/<conversation_id>', methods=['GET'])
@login_required
def get_conversation(conversation_id):
    """获取单个对话详情"""
    conversation = db.get_conversation(conversation_id)

    if not conversation:
        return jsonify({'error': '对话不存在'}), 404

    return jsonify(conversation)


@app.route('/api/conversations', methods=['POST'])
@login_required
def create_conversation_endpoint():
    """创建新对话"""
    conv_id = db.create_conversation()
    conversation = db.get_conversation(conv_id)

    return jsonify({
        'id': conv_id,
        'title': conversation['title'],
        'timestamp': conversation['created_at']
    })


@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
@login_required
def delete_conversation_endpoint(conversation_id):
    """删除对话"""
    success = db.delete_conversation(conversation_id)

    if not success:
        return jsonify({'error': '对话不存在'}), 404

    conversations = db.list_conversations(limit=1)
    new_current_id = conversations[0]['id'] if conversations else None

    return jsonify({
        'success': True,
        'new_current_id': new_current_id
    })


@app.route('/api/kb/status', methods=['GET'])
@login_required
def kb_status():
    """获取知识库状态"""
    return jsonify({
        'ready': qa_system.is_db_ready(),
        'documents': kb_builder.list_documents(),
        'categories': kb_builder.list_documents_by_category()
    })


@app.route('/api/kb/categories', methods=['GET'])
@admin_required
def get_categories():
    """获取文档分类列表（仅管理员）"""
    from build_db import DocumentCategory
    return jsonify(DocumentCategory.get_all_categories())


@app.route('/api/kb/documents', methods=['GET'])
@admin_required
def get_documents_by_category():
    """获取按分类组织的文档列表（仅管理员）"""
    return jsonify(kb_builder.list_documents_by_category())


@app.route('/api/students', methods=['GET'])
@admin_required
def get_students():
    """获取学生列表（仅管理员）"""
    students = user_manager.list_students()
    return jsonify(students)


@app.route('/api/students', methods=['POST'])
@admin_required
def create_student():
    """创建学生账号（仅管理员）"""
    data = request.json
    
    username = data.get('username', '').strip()
    name = data.get('name', '').strip()
    password = data.get('password', '')
    
    if not username or not name or not password:
        return jsonify({'error': '请填写所有字段'}), 400
    
    success = user_manager.add_user(username, password, 'student', name)
    
    if success:
        logger.info(f"学生账号已创建: {username}")
        return jsonify({'success': True, 'message': f'学生账号 {username} 创建成功'})
    else:
        return jsonify({'error': '该学号已存在'}), 400


@app.route('/api/students/<username>', methods=['DELETE'])
@admin_required
def delete_student(username):
    """删除学生账号（仅管理员）"""
    success = user_manager.delete_user(username)
    
    if success:
        logger.info(f"学生账号已删除: {username}")
        return jsonify({'success': True, 'message': f'学生账号 {username} 已删除'})
    else:
        return jsonify({'error': '删除失败，账号不存在或为管理员账号'}), 400


@app.route('/api/kb/upload', methods=['POST'])
@admin_required
def upload_document():
    """上传文档到知识库（仅管理员）"""
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '文件名为空'}), 400

    allowed_extensions = {'.txt', '.pdf'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        return jsonify({'error': f'不支持的文件格式: {ext}'}), 400

    category = request.form.get('category', 'other')
    
    filename = safe_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    try:
        count = kb_builder.process_documents([file_path], category=category)
        qa_system.reload_vector_store()

        logger.info(f"文档上传成功: {filename}, 分类: {category}")

        return jsonify({
            'success': True,
            'message': f'成功处理 {count} 个文档片段',
            'document': filename,
            'category': category
        })
    except Exception as e:
        logger.error(f"文档处理失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/kb/documents/<doc_name>', methods=['DELETE'])
@admin_required
def delete_document(doc_name):
    """删除知识库中的文档（仅管理员）"""
    success = kb_builder.delete_document(doc_name)

    if success:
        qa_system.reload_vector_store()
        logger.info(f"文档删除成功: {doc_name}")
        return jsonify({'success': True, 'message': f'已删除 {doc_name}'})
    else:
        return jsonify({'error': '删除失败'}), 400


@app.route('/api/kb/clear', methods=['POST'])
@admin_required
def clear_kb():
    """清空知识库（仅管理员）"""
    kb_builder.clear_all()
    qa_system.reload_vector_store()
    logger.info("知识库已清空")
    return jsonify({'success': True, 'message': '知识库已清空'})


def open_browser():
    """自动打开浏览器"""
    import webbrowser
    import time
    time.sleep(1.5)
    webbrowser.open(f'http://localhost:{Config.FLASK_PORT}')


if __name__ == '__main__':
    import threading

    print("=" * 50)
    print("高校事务智能问答系统 (Flask)")
    print("=" * 50)
    print(f"\n启动中...")
    print(f"访问地址: http://localhost:{Config.FLASK_PORT}")
    print("\n按 Ctrl+C 停止服务")
    print("=" * 50 + "\n")

    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()

    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG,
        use_reloader=False
    )
