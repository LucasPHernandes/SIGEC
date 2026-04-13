import os
from datetime import datetime, timedelta
from functools import wraps
import pandas as pd
import re
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from werkzeug.utils import secure_filename
from werkzeug.utils import secure_filename
import tempfile
from werkzeug.security import generate_password_hash
import sys
import csv
import io
from queue import Queue
from flask import Response
import json


print(f"Python sendo usado: {sys.executable}")
print(f"Path: {sys.path}")

from flask import (
    Flask, render_template, request, redirect, url_for, 
    flash, jsonify, session, send_file, abort, Blueprint
)
from flask_login import (
    LoginManager, login_user, logout_user, 
    login_required, current_user
)
from flask_migrate import Migrate

from models import (
    db, Usuario, Setor, Turma, Aluno, TipoOcorrencia, Ocorrencia, 
    HistoricoOcorrencia, Anexo, Disciplina, TurmaDisciplina, Nota, 
    Frequencia, Conselho, ConselhoAluno,
    Aviso, CalendarioEvento,
    ConselhoVersao, ConselhoAlunoVersao, ModeloEncaminhamento
)

app = Flask(__name__)
class PrefixMiddleware:
    def __init__(self, app, prefix='/sigec'):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        
        if path == '/':
            start_response('302 Found', [('Location', self.prefix + '/')])
            return []
        
        if path.startswith(self.prefix):
            environ['PATH_INFO'] = path[len(self.prefix):]
            if not environ['PATH_INFO']:
                environ['PATH_INFO'] = '/'
            environ['SCRIPT_NAME'] = self.prefix
        
        return self.app(environ, start_response)

app.wsgi_app = PrefixMiddleware(app.wsgi_app)

app.config['APPLICATION_ROOT'] = '/sigec'


app.config['SECRET_KEY'] = 'chave-super-secreta-iffar-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}


# Inicializa extensões
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'

@login_manager.unauthorized_handler
def unauthorized():
    # Remove o prefixo do next se existir
    next_url = request.args.get('next', '')
    if next_url and next_url.startswith('/sigec'):
        next_url = next_url[6:]
    
    # Redireciona para o login com o next limpo
    return redirect(url_for('login', next=next_url))

# Garante que a pasta de uploads existe
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'fotos'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'anexos'), exist_ok=True)


conselho_event_queues = {}



# Decorator para verificar permissões
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            if current_user.role not in roles and not current_user.is_admin():
                flash('Você não tem permissão para acessar esta página.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def conselho_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if not current_user.pode_criar_conselho():
            flash('Apenas administradores, direção e equipe pedagógica podem acessar esta funcionalidade.', 'danger')
            return redirect(url_for('listar_conselhos'))
        return f(*args, **kwargs)
    return decorated_function

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Rotas principais

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario and usuario.check_senha(senha):
            # Verifica se é primeiro acesso
            if usuario.primeiro_acesso:
                flash('Este é seu primeiro acesso. Por favor, defina sua senha.', 'warning')
                return redirect(url_for('primeiro_acesso', token=usuario.matricula or usuario.email))
            
            login_user(usuario)
            usuario.ultimo_acesso = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('dashboard'))
        else:
            flash('E-mail ou senha incorretos!', 'danger')
    
    return render_template('login.html')

@app.route('/sigec')
def redirect_sigec():
    return redirect('/sigec/')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('index'))

@app.route('/primeiro-acesso', methods=['GET', 'POST'])
def primeiro_acesso():
    token = request.args.get('token')
    if not token:
        flash('Token inválido!', 'danger')
        return redirect(url_for('login'))
    
    # Busca usuário pelo token (usando matrícula ou email como token)
    usuario = Usuario.query.filter_by(matricula=token).first()
    if not usuario:
        usuario = Usuario.query.filter_by(email=token).first()
    
    if not usuario or not usuario.primeiro_acesso:
        flash('Link inválido ou usuário já definiu sua senha!', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        senha = request.form.get('senha')
        confirmar_senha = request.form.get('confirmar_senha')
        
        if not senha or len(senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres!', 'danger')
            return redirect(url_for('primeiro_acesso', token=token))
        
        if senha != confirmar_senha:
            flash('As senhas não coincidem!', 'danger')
            return redirect(url_for('primeiro_acesso', token=token))
        
        usuario.set_senha(senha)
        usuario.primeiro_acesso = False
        db.session.commit()
        
        flash('Senha definida com sucesso! Faça login para continuar.', 'success')
        return redirect(url_for('login'))
    
    return render_template('primeiro_acesso.html', usuario=usuario)

@app.route('/recuperar-senha', methods=['GET', 'POST'])
def recuperar_senha():
    if request.method == 'POST':
        email = request.form.get('email')
        usuario = Usuario.query.filter_by(email=email).first()
        
        if not usuario:
            flash('E-mail não encontrado!', 'danger')
            return redirect(url_for('recuperar_senha'))
        
        token = usuario.matricula if usuario.matricula else usuario.email
        
        link = url_for('resetar_senha', token=token, _external=True)
        
        flash(f'Link de recuperação gerado! Acesse: {link}', 'info')
        return redirect(url_for('login'))
    
    return render_template('recuperar_senha.html')

@app.route('/resetar-senha', methods=['GET', 'POST'])
def resetar_senha():
    token = request.args.get('token')
    if not token:
        flash('Token inválido!', 'danger')
        return redirect(url_for('login'))
    
    # Busca usuário pelo token
    usuario = Usuario.query.filter_by(matricula=token).first()
    if not usuario:
        usuario = Usuario.query.filter_by(email=token).first()
    
    if not usuario:
        flash('Usuário não encontrado!', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        senha = request.form.get('senha')
        confirmar_senha = request.form.get('confirmar_senha')
        
        if not senha or len(senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres!', 'danger')
            return redirect(url_for('resetar_senha', token=token))
        
        if senha != confirmar_senha:
            flash('As senhas não coincidem!', 'danger')
            return redirect(url_for('resetar_senha', token=token))
        
        usuario.set_senha(senha)
        db.session.commit()
        
        flash('Senha alterada com sucesso! Faça login para continuar.', 'success')
        return redirect(url_for('login'))
    
    return render_template('resetar_senha.html', usuario=usuario)

@app.route('/dashboard')
@login_required
def dashboard():
    # Dados comuns a todos os usuários
    conselhos_abertos = Conselho.query.filter_by(status='aberto').all()
    
    # Dados específicos por role
    if current_user.role in ['admin', 'direcao', 'pedagogico']:
        # Visão administrativa/pedagógica
        total_alunos = Aluno.query.count()
        alunos_ativos = Aluno.query.filter_by(situacao='ativo').count()
        
        total_ocorrencias = Ocorrencia.query.count()
        ocorrencias_abertas = Ocorrencia.query.filter_by(status='aberta').count()
        ocorrencias_resolvidas = Ocorrencia.query.filter_by(status='resolvida').count()
        ocorrencias_atrasadas = Ocorrencia.query.filter(
            Ocorrencia.status != 'resolvida',
            Ocorrencia.data_prazo < datetime.utcnow()
        ).count()
        
        # Gráficos
        ocorrencias_por_setor = db.session.query(
            Setor.nome, db.func.count(Ocorrencia.id)
        ).join(Ocorrencia, Setor.id == Ocorrencia.setor_destino_id)\
         .group_by(Setor.id).all()
        
        ocorrencias_por_status = db.session.query(
            Ocorrencia.status, db.func.count(Ocorrencia.id)
        ).group_by(Ocorrencia.status).all()
        
        # Últimas ocorrências (todas)
        ultimas_ocorrencias = Ocorrencia.query.order_by(
            Ocorrencia.data_abertura.desc()
        ).limit(10).all()
        
        # Calendário e avisos (admin/direcao podem criar)
        pode_criar_evento = current_user.role in ['admin', 'direcao']
        pode_criar_aviso = current_user.role in ['admin', 'direcao']

        turmas = Turma.query.all()
        
        return render_template('dashboard.html',
                     role='admin',
                     total_alunos=total_alunos,
                     alunos_ativos=alunos_ativos,
                     total_ocorrencias=total_ocorrencias,
                     ocorrencias_abertas=ocorrencias_abertas,
                     ocorrencias_resolvidas=ocorrencias_resolvidas,
                     ocorrencias_atrasadas=ocorrencias_atrasadas,
                     ocorrencias_por_setor=ocorrencias_por_setor,
                     ocorrencias_por_status=ocorrencias_por_status,
                     ultimas_ocorrencias=ultimas_ocorrencias,
                     conselhos_abertos=conselhos_abertos,
                     turmas=turmas,  # NOVO
                     pode_criar_evento=pode_criar_evento,
                     pode_criar_aviso=pode_criar_aviso)
    
    elif current_user.role == 'professor':
        # Visão do professor
        total_alunos = Aluno.query.count()  # Total de alunos da escola
        
        # Ocorrências criadas pelo professor
        minhas_ocorrencias = Ocorrencia.query.filter_by(
            usuario_criador_id=current_user.id
        ).order_by(Ocorrencia.data_abertura.desc()).limit(10).all()
        
        total_minhas_ocorrencias = Ocorrencia.query.filter_by(
            usuario_criador_id=current_user.id
        ).count()
        
        minhas_ocorrencias_abertas = Ocorrencia.query.filter_by(
            usuario_criador_id=current_user.id,
            status='aberta'
        ).count()
        
        return render_template('dashboard.html',
                             role='professor',
                             total_alunos=total_alunos,
                             minhas_ocorrencias=minhas_ocorrencias,
                             total_minhas_ocorrencias=total_minhas_ocorrencias,
                             minhas_ocorrencias_abertas=minhas_ocorrencias_abertas,
                             conselhos_abertos=conselhos_abertos)
    
    else:
        # Visão para outros roles (assistente, saúde, etc)
        return render_template('dashboard.html',
                             role='outros',
                             conselhos_abertos=conselhos_abertos)

# Rotas de alunos
@app.route('/alunos')
@login_required
def listar_alunos():
    page = request.args.get('page', 1, type=int)
    busca = request.args.get('busca', '')
    turma_id = request.args.get('turma', type=int)
    interno = request.args.get('interno', type=bool)  # NOVO FILTRO
    
    query = Aluno.query
    
    if busca:
        query = query.filter(
            db.or_(
                Aluno.nome.contains(busca),
                Aluno.matricula.contains(busca),
                Aluno.cpf.contains(busca)
            )
        )
    
    if turma_id:
        query = query.filter_by(turma_id=turma_id)
    
    if interno is not None:
        query = query.filter_by(interno=interno)
    
    alunos = query.order_by(Aluno.nome).paginate(page=page, per_page=20)
    turmas = Turma.query.all()
    
    return render_template('alunos/listar.html', 
                         alunos=alunos, 
                         turmas=turmas, 
                         busca=busca,
                         interno=interno)

@app.route('/alunos/novo', methods=['GET', 'POST'])
@login_required
def novo_aluno():
    if request.method == 'POST':
        # Processa dados do formulário
        aluno = Aluno(
            nome=request.form['nome'],
            matricula=request.form['matricula'],
            data_nascimento=datetime.strptime(request.form['data_nascimento'], '%Y-%m-%d') if request.form['data_nascimento'] else None,
            cpf=request.form['cpf'],
            email=request.form['email'],
            telefone=request.form['telefone'],
            endereco=request.form['endereco'],
            turma_id=request.form['turma_id'] if request.form['turma_id'] else None,
            situacao=request.form['situacao'],
            observacoes=request.form['observacoes']
        )
        
        # Processa foto
        if 'foto' in request.files:
            foto = request.files['foto']
            if foto and foto.filename:
                filename = secure_filename(f"{aluno.matricula}_{foto.filename}")
                caminho = os.path.join(app.config['UPLOAD_FOLDER'], 'fotos', filename)
                foto.save(caminho)
                aluno.foto = f"uploads/fotos/{filename}"
        
        db.session.add(aluno)
        db.session.commit()
        
        flash('Aluno cadastrado com sucesso!', 'success')
        return redirect(url_for('listar_alunos'))
    
    turmas = Turma.query.all()
    return render_template('alunos/cadastrar.html', turmas=turmas)

@app.route('/alunos/<int:id>')
@login_required
def ver_aluno(id):
    aluno = Aluno.query.get_or_404(id)
    
    # Busca ocorrências do aluno
    ocorrencias = Ocorrencia.query.filter_by(aluno_id=id).order_by(
        Ocorrencia.data_abertura.desc()
    ).all()
    
    # Estatísticas do aluno
    total_ocorrencias = len(ocorrencias)
    ocorrencias_abertas = sum(1 for o in ocorrencias if o.status == 'aberta')
    ocorrencias_resolvidas = sum(1 for o in ocorrencias if o.status == 'resolvida')
    
    # Busca notas do aluno por disciplina
    from sqlalchemy import func
    
    # Ano e semestre atuais
    ano_atual = datetime.now().year
    semestre_atual = 1 if datetime.now().month <= 6 else 2
    
    # Busca todas as notas do aluno no semestre atual
    notas_aluno = db.session.query(
        Disciplina,
        Nota,
        TurmaDisciplina
    ).join(
        TurmaDisciplina, TurmaDisciplina.disciplina_id == Disciplina.id
    ).join(
        Nota, Nota.turma_disciplina_id == TurmaDisciplina.id
    ).filter(
        Nota.aluno_id == aluno.id,
        TurmaDisciplina.ano == ano_atual,
        TurmaDisciplina.semestre == semestre_atual
    ).all()
    
    # Formata os dados para o template
    disciplinas_notas = []
    for disciplina, nota, turma_disciplina in notas_aluno:
        disciplinas_notas.append({
            'disciplina': disciplina.nome,
            'codigo': disciplina.codigo,
            'nota_parcial1': nota.nota_parcial1,
            'nota_sem1': nota.nota_sem1,
            'nota_parcial2': nota.nota_parcial2,
            'nota_sem2': nota.nota_sem2,
            # Flags para saber se está abaixo da média em cada período
            'parcial1_abaixo': nota.nota_parcial1 < 7.0 if nota.nota_parcial1 is not None else None,
            'sem1_abaixo': nota.nota_sem1 < 7.0 if nota.nota_sem1 is not None else None,
            'parcial2_abaixo': nota.nota_parcial2 < 7.0 if nota.nota_parcial2 is not None else None,
            'sem2_abaixo': nota.nota_sem2 < 7.0 if nota.nota_sem2 is not None else None
        })
    
    # Ordena por nome da disciplina
    disciplinas_notas.sort(key=lambda x: x['disciplina'])
    
    return render_template('alunos/perfil.html',
                         aluno=aluno,
                         ocorrencias=ocorrencias,
                         total_ocorrencias=total_ocorrencias,
                         ocorrencias_abertas=ocorrencias_abertas,
                         ocorrencias_resolvidas=ocorrencias_resolvidas,
                         disciplinas_notas=disciplinas_notas,
                         ano_atual=ano_atual,
                         semestre_atual=semestre_atual)

# Rotas de ocorrências
@app.route('/ocorrencias')
@login_required
def listar_ocorrencias():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    setor_id = request.args.get('setor', type=int)
    aluno_id = request.args.get('aluno', type=int)
    id_busca = request.args.get('id_busca', type=int)  # NOVO: busca por ID
    
    query = Ocorrencia.query
    
    # SE FOR BUSCA POR ID ESPECÍFICO, PRIORIZA
    if id_busca:
        ocorrencia = Ocorrencia.query.get(id_busca)
        if ocorrencia:
            # Verifica permissão para ver esta ocorrência
            if current_user.pode_ver_todas_ocorrencias() or \
               ocorrencia.setor_origem_id == current_user.setor_id or \
               ocorrencia.setor_destino_id == current_user.setor_id or \
               ocorrencia.usuario_criador_id == current_user.id or \
               ocorrencia.usuario_atendente_id == current_user.id:
                query = query.filter(Ocorrencia.id == id_busca)
            else:
                flash('Você não tem permissão para ver esta ocorrência.', 'danger')
                return redirect(url_for('listar_ocorrencias'))
        else:
            flash(f'Ocorrência com ID #{id_busca} não encontrada.', 'warning')
            # Retorna para a lista normal sem o filtro
            return redirect(url_for('listar_ocorrencias'))
    
    # Filtros normais (apenas se não for busca por ID)
    if not id_busca:
        if not current_user.pode_ver_todas_ocorrencias():
            query = query.filter(
                db.or_(
                    Ocorrencia.setor_origem_id == current_user.setor_id,
                    Ocorrencia.setor_destino_id == current_user.setor_id,
                    Ocorrencia.usuario_criador_id == current_user.id,
                    Ocorrencia.usuario_atendente_id == current_user.id
                )
            )
        
        if status:
            query = query.filter_by(status=status)
        
        if setor_id:
            query = query.filter(
                db.or_(
                    Ocorrencia.setor_origem_id == setor_id,
                    Ocorrencia.setor_destino_id == setor_id
                )
            )
        
        if aluno_id:
            query = query.filter_by(aluno_id=aluno_id)
    
    ocorrencias = query.order_by(
        Ocorrencia.data_abertura.desc()
    ).paginate(page=page, per_page=15)
    
    setores = Setor.query.all()
    tipos = TipoOcorrencia.query.all()
    alunos = Aluno.query.filter_by(situacao='ativo').order_by(Aluno.nome).all()  # NOVO: para o filtro de aluno
    
    return render_template('ocorrencias/listar.html',
                         ocorrencias=ocorrencias,
                         setores=setores,
                         tipos=tipos,
                         alunos=alunos)  # NOVO: passar alunos para o template

@app.route('/ocorrencias/nova', methods=['GET', 'POST'])
@login_required
def nova_ocorrencia():
    if not current_user.pode_criar_ocorrencia():
        flash('Você não tem permissão para criar ocorrências.', 'danger')
        return redirect(url_for('listar_ocorrencias'))
    
    # VERIFICA SE O USUÁRIO TEM SETOR
    if not current_user.setor_id:
        flash('Você precisa estar vinculado a um setor para criar ocorrências.', 'danger')
        return redirect(url_for('listar_ocorrencias'))
    
    if request.method == 'POST':

        ocorrencia = Ocorrencia(
            titulo=request.form['titulo'],
            descricao=request.form['descricao'],
            aluno_id=request.form['aluno_id'],
            tipo_id=request.form['tipo_id'],
            setor_origem_id=request.form.get('setor_origem_id', current_user.setor_id),
            setor_destino_id=request.form['setor_destino_id'],
            usuario_criador_id=current_user.id,
            prioridade=request.form['prioridade'],
            status='aberta'
        )
        
        # Define prazo baseado no tipo
        tipo = TipoOcorrencia.query.get(request.form['tipo_id'])
        if tipo and tipo.prazo_dias:
            ocorrencia.data_prazo = datetime.utcnow() + timedelta(days=tipo.prazo_dias)
        
        db.session.add(ocorrencia)
        db.session.flush()
        
        historico = HistoricoOcorrencia(
            ocorrencia_id=ocorrencia.id,
            usuario_id=current_user.id,
            acao='criacao',
            descricao='Ocorrência criada'
        )
        db.session.add(historico)
        
        # Processa anexos
        if 'anexos' in request.files:
            arquivos = request.files.getlist('anexos')
            for arquivo in arquivos:
                if arquivo and arquivo.filename:
                    filename = secure_filename(f"{ocorrencia.id}_{datetime.utcnow().timestamp()}_{arquivo.filename}")
                    caminho = os.path.join(app.config['UPLOAD_FOLDER'], 'anexos', filename)
                    arquivo.save(caminho)
                    
                    anexo = Anexo(
                        ocorrencia_id=ocorrencia.id,
                        nome_arquivo=arquivo.filename,
                        caminho_arquivo=f"uploads/anexos/{filename}",
                        tipo_arquivo=arquivo.content_type,
                        usuario_id=current_user.id
                    )
                    db.session.add(anexo)
        
        db.session.commit()
        
        flash('Ocorrência criada com sucesso!', 'success')
        return redirect(url_for('ver_ocorrencia', id=ocorrencia.id))
    
    alunos = Aluno.query.filter_by(situacao='ativo').order_by(Aluno.nome).all()
    setores = Setor.query.filter(Setor.id != current_user.setor_id).all()
    tipos = TipoOcorrencia.query.all()
    
    return render_template('ocorrencias/criar.html',
                         alunos=alunos,
                         setores=setores,
                         tipos=tipos)

@app.route('/ocorrencias/<int:id>')
@login_required
def ver_ocorrencia(id):
    ocorrencia = Ocorrencia.query.get_or_404(id)
    
    # Verifica permissão
    if not current_user.pode_ver_todas_ocorrencias():
        if (ocorrencia.setor_origem_id != current_user.setor_id and 
            ocorrencia.setor_destino_id != current_user.setor_id and
            ocorrencia.usuario_criador_id != current_user.id and
            ocorrencia.usuario_atendente_id != current_user.id):
            flash('Você não tem permissão para ver esta ocorrência.', 'danger')
            return redirect(url_for('listar_ocorrencias'))
    
    return render_template('ocorrencias/ver.html', ocorrencia=ocorrencia)

@app.route('/ocorrencias/<int:id>/atualizar', methods=['POST'])
@login_required
def atualizar_ocorrencia(id):
    ocorrencia = Ocorrencia.query.get_or_404(id)
    
    novo_status = request.form.get('status')
    comentario = request.form.get('comentario')
    
    if novo_status and novo_status != ocorrencia.status:
        ocorrencia.status = novo_status
        
        if novo_status == 'resolvida':
            ocorrencia.data_conclusao = datetime.utcnow()
        
        # Adiciona histórico
        historico = HistoricoOcorrencia(
            ocorrencia_id=ocorrencia.id,
            usuario_id=current_user.id,
            acao='mudanca_status',
            descricao=f'Status alterado para {novo_status}'
        )
        db.session.add(historico)
    
    if comentario:
        historico = HistoricoOcorrencia(
            ocorrencia_id=ocorrencia.id,
            usuario_id=current_user.id,
            acao='comentario',
            descricao=comentario
        )
        db.session.add(historico)
    
    db.session.commit()
    
    flash('Ocorrência atualizada com sucesso!', 'success')
    return redirect(url_for('ver_ocorrencia', id=id))

def identificar_turma(nome_aba):
    """
    Identifica o curso e ano baseado no nome da aba
    Padrão: T11, T12, T13, T14, T15, T16, T21, T22, T23, T24, T31, T32
    """
    
    # Mapeamento completo
    mapeamento = {
        # Primeiro Ano
        'T11': {'ano': 1, 'curso': 'Técnico em Agropecuária Integrado', 'turma': '1° Ano Agropecuária - T11'},
        'T12': {'ano': 1, 'curso': 'Técnico em Agropecuária Integrado', 'turma': '1° Ano Agropecuária - T12'},
        'T13': {'ano': 1, 'curso': 'Técnico em Agropecuária Integrado', 'turma': '1° Ano Agropecuária - T13'},
        
        'T14': {'ano': 1, 'curso': 'Técnico em Informática Integrado', 'turma': '1° Ano Informática - T14'},
        'T15': {'ano': 1, 'curso': 'Técnico em Administração Integrado', 'turma': '1° Ano Administração - T15'},
        'T16': {'ano': 1, 'curso': 'Técnico em Informática Integrado', 'turma': '1° Ano Informática - T16'},
        
        # Segundo Ano
        'T21': {'ano': 2, 'curso': 'Técnico em Agropecuária Integrado', 'turma': '2° Ano Agropecuária - T21'},
        'T22': {'ano': 2, 'curso': 'Técnico em Agropecuária Integrado', 'turma': '2° Ano Agropecuária - T22'},
        'T23': {'ano': 2, 'curso': 'Técnico em Agropecuária Integrado', 'turma': '2° Ano Agropecuária - T23'},
        
        'T24': {'ano': 2, 'curso': 'Técnico em Informática Integrado', 'turma': '2° Ano Informática - T24'},
        'T25': {'ano': 2, 'curso': 'Técnico em Administração Integrado', 'turma': '2° Ano Administração - T25'},
        
        # Terceiro Ano
        'T31': {'ano': 3, 'curso': 'Técnico em Agropecuária Integrado', 'turma': '3° Ano Agropecuária - T31'},
        'T32': {'ano': 3, 'curso': 'Técnico em Agropecuária Integrado', 'turma': '3° Ano Agropecuária - T32'},
        'T33': {'ano': 3, 'curso': 'Técnico em Agropecuária Integrado', 'turma': '3° Ano Agropecuária - T33'},

        'T34': {'ano': 3, 'curso': 'Técnico em Informática Integrado', 'turma': '3° Ano Informática - T34'},
        'T36': {'ano': 3, 'curso': 'Técnico em Informática Integrado', 'turma': '3° Ano Informática - T36'},
        'T35': {'ano': 3, 'curso': 'Técnico em Administração Integrado', 'turma': '3° Ano Administração - T35'},
    }
    
    return mapeamento.get(nome_aba, {
        'ano': 1,
        'curso': 'Técnico Integrado',
        'turma': f'{nome_aba} - 1° Ano'
    })

@app.route('/importar/planilha', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def importar_planilha():
    """
    Importa dados da planilha Subsídio T34.xlsx
    Cria turmas, disciplinas, alunos e notas automaticamente
    """
    
    if request.method == 'GET':
        return render_template('importar_planilha.html')
    
    if 'arquivo' not in request.files:
        flash('Nenhum arquivo enviado', 'danger')
        return redirect(request.url)
    
    arquivo = request.files['arquivo']
    if arquivo.filename == '':
        flash('Nenhum arquivo selecionado', 'danger')
        return redirect(request.url)
    
    if not arquivo.filename.endswith(('.xlsx', '.xls')):
        flash('Formato inválido. Envie um arquivo Excel (.xlsx ou .xls)', 'danger')
        return redirect(request.url)
    
    
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, secure_filename(arquivo.filename))
    arquivo.save(temp_path)
    
    try:
        # Processa a importação
        resultado = processar_importacao_planilha(temp_path)
        
        # Remove arquivo temporário
        os.remove(temp_path)
        
        if resultado['sucesso']:
            flash(f'✅ Importação concluída! {resultado["resumo"]}', 'success')
        else:
            flash(f'❌ Erro na importação: {resultado["erro"]}', 'danger')
        
        return redirect(url_for('listar_alunos'))
        
    except Exception as e:
        flash(f'Erro inesperado: {str(e)}', 'danger')
        return redirect(url_for('importar_planilha'))

def debug_print_planilha(caminho_arquivo, nome_aba='T34'):
    """Função para debug - mostra a estrutura da planilha"""
    
    print(f"\n{'='*50}")
    print(f"DEBUG - Analisando aba: {nome_aba}")
    print('='*50)
    
    # Carrega a planilha
    df = pd.read_excel(caminho_arquivo, sheet_name=nome_aba, header=None)
    
    print(f"\nPrimeiras 5 linhas da planilha:")
    print(df.head())
    
    print(f"\nColunas encontradas (índice 0-30):")
    for i in range(min(30, len(df.columns))):
        if i < len(df.columns):
            valor = df.iloc[1, i] if len(df) > 1 else None
            print(f"Coluna {i}: {valor}")
    
    # DEBUG ESPECÍFICO: Mostra todas as colunas que contêm "Parcial"
    print(f"\n{'='*30}")
    print("COLUNAS COM 'Parcial' NA T34:")
    print('='*30)
    for i in range(len(df.columns)):
        if i < len(df.columns):
            valor = df.iloc[1, i] if len(df) > 1 else ''
            if 'Parcial' in str(valor):
                print(f"Coluna {i}: {valor}")
    
    # Procura especificamente pelas colunas de nota do Adriano
    print(f"\nBuscando dados do Adriano...")
    for idx, row in df.iterrows():
        if idx >= 2:  # Pula cabeçalhos
            nome = str(row.get(1, '')).strip() if len(row) > 1 else ''
            if 'ADRIANO CAUDURO' in nome.upper():
                print(f"\nLinha {idx} - Aluno: {nome}")
                print(f"Dados completos da linha:")
                for col_idx, valor in enumerate(row):
                    if pd.notna(valor):
                        print(f"  Coluna {col_idx}: {valor}")
    
    return df        

def processar_importacao_planilha(caminho_arquivo):
    """
    Processa a planilha e importa os dados para o banco
    Inclui: turmas, disciplinas, alunos, notas dos 4 períodos e frequência
    """
    
    resultado = {
        'sucesso': False,
        'resumo': '',
        'erro': '',
        'estatisticas': {
            'turmas': 0,
            'alunos': 0,
            'disciplinas': 0,
            'notas_parciais': 0,
            'notas_semestrais': 0,
            'alunos_internos': 0
        },
        'debug': []
    }
    
    try:
        # DEBUG: mostra estrutura da aba T34
        debug_print_planilha(caminho_arquivo, 'T34')
        
        # Carrega todas as abas
        todas_abas = pd.read_excel(caminho_arquivo, sheet_name=None, header=None)
        
        # Mapa de siglas para disciplinas
        mapa_disciplinas = {
            'A.G.': 'Agricultura Geral',
            'ART': 'Arte',
            'BIO': 'Biologia',
            'EDF': 'Educação Física',
            'FIL': 'Filosofia',
            'FIS': 'Física',
            'GEO': 'Geografia',
            'HIS': 'História',
            'I.B.': 'Informática Básica',
            'ING': 'Língua Inglesa',
            'PORT': 'Língua Portuguesa e Literatura Brasileira',
            'MAT': 'Matemática',
            'QUI': 'Química',
            'SOC': 'Sociologia',
            'Z.G.': 'Zootecnia Geral',
            'FI': 'Fundamentos da Informática',
            'HARD1': 'Hardware I',
            'IELETRO': 'Introdução a Eletrônica',
            'ELETRO': 'Introdução a Eletrônica',
            'PR1': 'Programação I',
            'PR2': 'Programação II',
            'PR3': 'Programação III',
            'AG I': 'Agricultura I',
            'FOR': 'Forragicultura',
            'INFRA1': 'Infraestrutura I',
            'SOL': 'Solos',
            'ZOO1': 'Zootecnia I',
            'AMDS': 'Análise e Modelagem de Sistemas',
            'BD': 'Banco de Dados',
            'HWII': 'Hardware II',
            'REDI': 'Redes de Computadores I',
            'AG II': 'Agricultura II',
            'AG III': 'Agricultura III',
            'E.R.': 'Extensão Rural',
            'GEP': 'Gestão, Economia e Projetos',
            'INFRA2': 'Infraestrutura II',
            'TAL': 'Tecnologia de Alimentos',
            'ZOO2': 'Zootecnia II',
            'CTB': 'Contabilidade',
            'MKT': 'Fundamentos de Marketing e Vendas',
            'GP': 'Gestão de Pessoas',
            'PROD': 'Produção e Logística',
            'MF': 'Matemática Financeira',
            'NE': 'Noções de Economia',
            'RA': 'Rotinas Administrativas',
            'FA': 'Fundamentos da Administração',
            'INFO': 'Informática',
            'REDII': 'Redes de Computadores II',
            'TEI': 'Tópicos Especiais em Informática',
            'ADMF': 'Administração Financeira',
            'DIR': 'Direito',
            'EMP': 'Empreendedorismo',
            'GARS': 'Gestão Ambiental e Responsabilidade Social',
            'TEA': 'Tópicos Especiais em Administração'
        }
        
        # 1. CRIA TODAS AS DISCIPLINAS
        disciplinas_cache = {}
        siglas_encontradas = set()
        
        for nome_aba, df in todas_abas.items():
            if nome_aba == "Como preencher":
                continue
            
            print(f"\nProcessando aba: {nome_aba}")
            cabecalhos = df.iloc[1].tolist() if len(df) > 1 else []
            
            for i, col in enumerate(cabecalhos):
                if pd.isna(col):
                    continue
                col_str = str(col)
                match = re.search(r'\(([^)]+)\)', col_str)
                if match:
                    sigla = match.group(1)
                    siglas_encontradas.add(sigla)
                    print(f"  Encontrada sigla: {sigla} na coluna {i}")
        
        print(f"\nSiglas encontradas: {siglas_encontradas}")
        
        for sigla in siglas_encontradas:
            nome_completo = mapa_disciplinas.get(sigla, sigla)
            disciplina = Disciplina.query.filter_by(codigo=sigla).first()
            if not disciplina:
                disciplina = Disciplina(
                    nome=nome_completo,
                    codigo=sigla,
                    carga_horaria=80
                )
                db.session.add(disciplina)
                db.session.flush()
                resultado['estatisticas']['disciplinas'] += 1
                print(f"  Disciplina criada: {sigla} - {nome_completo}")
            disciplinas_cache[sigla] = disciplina.id
        
        db.session.commit()
        
        # 2. PROCESSA CADA TURMA
        ano_atual = datetime.now().year
        semestre_atual = 1 if datetime.now().month <= 6 else 2
        
        abas_validas = [aba for aba in todas_abas.keys() if aba != "Como preencher"]
        
        for nome_aba in abas_validas:
            df = todas_abas[nome_aba]
            
            info_turma = identificar_turma(nome_aba)
            print(f"\nProcessando turma: {nome_aba} -> {info_turma['turma']}")
            
            cabecalhos = df.iloc[1].tolist() if len(df) > 1 else []
            dados = df.iloc[2:].copy() if len(df) > 2 else pd.DataFrame()
            dados.columns = cabecalhos
            dados = dados.loc[:, ~dados.columns.isna()]
            
            # Identifica colunas importantes
            col_matricula = None
            col_nome = None
            col_email = None
            col_nascimento = None
            col_cidade = None
            col_uf = None
            col_interno = None
            
            for i, col in enumerate(cabecalhos):
                if pd.isna(col):
                    continue
                col_str = str(col)
                if 'Nº Matrícula' in col_str or 'Matrícula' in col_str:
                    col_matricula = col
                    print(f"  Coluna matrícula: {col} (índice {i})")
                elif 'Nome do aluno' in col_str or 'Nome' in col_str:
                    col_nome = col
                    print(f"  Coluna nome: {col} (índice {i})")
                elif 'E-mail' in col_str or 'Email' in col_str:
                    col_email = col
                    print(f"  Coluna email: {col} (índice {i})")
                elif 'Nascimento' in col_str:
                    col_nascimento = col
                    print(f"  Coluna nascimento: {col} (índice {i})")
                elif 'Cidade' in col_str:
                    col_cidade = col
                    print(f"  Coluna cidade: {col} (índice {i})")
                elif 'UF' in col_str:
                    col_uf = col
                    print(f"  Coluna UF: {col} (índice {i})")
                elif 'Interno' in col_str:
                    col_interno = col
                    print(f"  Coluna interno: {col} (índice {i})")
            
            if not col_matricula or not col_nome:
                print(f"  AVISO: Aba {nome_aba} não tem colunas de matrícula/nome")
                continue
            
            # CRIA OU BUSCA TURMA
            turma_nome = info_turma['turma']
            turma = Turma.query.filter_by(nome=turma_nome).first()
            
            if not turma:
                turma = Turma(
                    nome=turma_nome,
                    curso=info_turma['curso'],
                    ano=info_turma['ano'],
                    turno='manha'
                )
                db.session.add(turma)
                db.session.flush()
                resultado['estatisticas']['turmas'] += 1
                print(f"  Turma criada: {turma_nome}")
            
            # 3. CRIA OS ALUNOS E PROCESSA NOTAS
            for idx, row in dados.iterrows():
                try:
                    matricula = str(row.get(col_matricula, '')).strip()
                    if not matricula or matricula == 'nan':
                        continue
                    
                    if matricula.endswith('.0'):
                        matricula = matricula[:-2]
                    
                    nome = str(row.get(col_nome, '')).strip()
                    if not nome or nome == 'nan':
                        continue
                    
                    email = str(row.get(col_email, '')).strip() if col_email else None
                    if email == 'nan':
                        email = None
                    
                    # Processa data de nascimento
                    data_nascimento = None
                    if col_nascimento and col_nascimento in row.index:
                        try:
                            val_nasc = row[col_nascimento]
                            if pd.notna(val_nasc):
                                if isinstance(val_nasc, datetime):
                                    data_nascimento = val_nasc.date()
                                elif isinstance(val_nasc, str):
                                    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d/%m/%y']:
                                        try:
                                            data_nascimento = datetime.strptime(val_nasc, fmt).date()
                                            break
                                        except:
                                            continue
                        except Exception as e:
                            print(f"    Erro ao processar data de nascimento: {e}")
                    
                    # Processa cidade
                    cidade = None
                    if col_cidade and col_cidade in row.index:
                        val_cidade = row[col_cidade]
                        if pd.notna(val_cidade):
                            cidade = str(val_cidade).strip()
                    
                    # Processa UF
                    uf = None
                    if col_uf and col_uf in row.index:
                        val_uf = row[col_uf]
                        if pd.notna(val_uf):
                            uf = str(val_uf).strip().upper()
                    
                    # Processa informação de interno
                    interno = False
                    quarto = None
                    if col_interno and col_interno in row.index:
                        val_interno = row[col_interno]
                        if pd.notna(val_interno):
                            val_str = str(val_interno).strip()
                            interno = True
                            quarto = val_str
                            resultado['estatisticas']['alunos_internos'] += 1
                            if 'ADRIANO' in nome.upper():
                                print(f"    Aluno interno: {nome} - Quarto: {quarto}")
                    
                    # DEBUG: mostra dados do Adriano
                    if 'ADRIANO' in nome.upper():
                        print(f"\n  >>> ENCONTRADO ADRIANO na linha {idx+3}")
                        print(f"  Matrícula: {matricula}")
                        print(f"  Nome: {nome}")
                        print(f"  Nascimento: {data_nascimento}")
                        print(f"  Cidade: {cidade}")
                        print(f"  UF: {uf}")
                        print(f"  Interno: {interno} ({quarto})")
                    
                    # Busca aluno existente ou cria novo
                    aluno = Aluno.query.filter_by(matricula=matricula).first()
                    if not aluno:
                        aluno = Aluno(
                            nome=nome,
                            matricula=matricula,
                            email=email,
                            data_nascimento=data_nascimento,
                            cidade=cidade,
                            uf=uf,
                            interno=interno,
                            quarto=quarto if interno else None,
                            turma_id=turma.id,
                            situacao='ativo'
                        )
                        db.session.add(aluno)
                        db.session.flush()
                        resultado['estatisticas']['alunos'] += 1
                    else:
                        # Atualiza informações do aluno existente
                        aluno.data_nascimento = data_nascimento or aluno.data_nascimento
                        aluno.cidade = cidade or aluno.cidade
                        aluno.uf = uf or aluno.uf
                        aluno.interno = interno
                        aluno.quarto = quarto if interno else None
                    
                    # 4. PROCESSA AS 4 NOTAS POR DISCIPLINA
                    for sigla in disciplinas_cache.keys():
                        colunas = {
                            'parcial1': None,
                            'sem1': None,
                            'parcial2': None,
                            'sem2': None
                        }
                        
                        for i, col in enumerate(cabecalhos):
                            if pd.isna(col):
                                continue
                            col_str = str(col).strip()
                            
                            # Busca para Nota Parcial 1
                            if (('Parcial 1' in col_str or 'Parcial1' in col_str) and 
                                f'({sigla})' in col_str):
                                colunas['parcial1'] = col
                                if 'ADRIANO' in nome.upper():
                                    print(f"    Coluna Parcial1 {sigla}: {col} (índice {i})")
                            
                            # Busca para Semestral 1
                            elif ((('Sem, 1' in col_str or 'Sem 1' in col_str or 'Sem1' in col_str) and 
                                  f'({sigla})' in col_str) or
                                  (col_str.startswith('Sem, 1') and f'({sigla})' in col_str)):
                                colunas['sem1'] = col
                                if 'ADRIANO' in nome.upper():
                                    print(f"    Coluna Sem1 {sigla}: {col} (índice {i})")
                            
                            # Busca para Nota Parcial 2
                            elif (('Parcial 2' in col_str or 'Parcial2' in col_str) and 
                                  f'({sigla})' in col_str):
                                colunas['parcial2'] = col
                            
                            # Busca para Semestral 2
                            elif ((('Sem, 2' in col_str or 'Sem 2' in col_str or 'Sem2' in col_str) and 
                                  f'({sigla})' in col_str) or
                                  (col_str.startswith('Sem, 2') and f'({sigla})' in col_str)):
                                colunas['sem2'] = col
                        
                        valores = {}
                        for periodo, col in colunas.items():
                            if col and col in row.index:
                                try:
                                    val = row[col]
                                    if pd.notna(val):
                                        if isinstance(val, str):
                                            val = val.replace(',', '.')
                                        valores[periodo] = float(val)
                                        if 'ADRIANO' in nome.upper():
                                            print(f"    {periodo} {sigla}: {valores[periodo]}")
                                except (ValueError, TypeError) as e:
                                    if 'ADRIANO' in nome.upper():
                                        print(f"    Erro ao converter {periodo} {sigla}: {val}")
                        
                        if valores:
                            turma_disciplina = TurmaDisciplina.query.filter_by(
                                turma_id=turma.id,
                                disciplina_id=disciplinas_cache[sigla],
                                ano=ano_atual,
                                semestre=semestre_atual
                            ).first()
                            
                            if not turma_disciplina:
                                turma_disciplina = TurmaDisciplina(
                                    turma_id=turma.id,
                                    disciplina_id=disciplinas_cache[sigla],
                                    ano=ano_atual,
                                    semestre=semestre_atual
                                )
                                db.session.add(turma_disciplina)
                                db.session.flush()
                            
                            nota = Nota.query.filter_by(
                                aluno_id=aluno.id,
                                turma_disciplina_id=turma_disciplina.id
                            ).first()
                            
                            if not nota:
                                nota = Nota(
                                    aluno_id=aluno.id,
                                    turma_disciplina_id=turma_disciplina.id,
                                    nota_parcial1=valores.get('parcial1'),
                                    nota_sem1=valores.get('sem1'),
                                    nota_parcial2=valores.get('parcial2'),
                                    nota_sem2=valores.get('sem2')
                                )
                                db.session.add(nota)
                                
                                if valores.get('parcial1'): resultado['estatisticas']['notas_parciais'] += 1
                                if valores.get('sem1'): resultado['estatisticas']['notas_semestrais'] += 1
                                if valores.get('parcial2'): resultado['estatisticas']['notas_parciais'] += 1
                                if valores.get('sem2'): resultado['estatisticas']['notas_semestrais'] += 1
                            else:
                                if valores.get('parcial1'): nota.nota_parcial1 = valores['parcial1']
                                if valores.get('sem1'): nota.nota_sem1 = valores['sem1']
                                if valores.get('parcial2'): nota.nota_parcial2 = valores['parcial2']
                                if valores.get('sem2'): nota.nota_sem2 = valores['sem2']
                    
                    if resultado['estatisticas']['alunos'] % 10 == 0:
                        db.session.commit()
                
                except Exception as e:
                    print(f"Erro processando aluno: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            db.session.commit()
            print(f"Turma {nome_aba} processada: {resultado['estatisticas']['alunos']} alunos, {resultado['estatisticas']['alunos_internos']} internos")
        
        total_notas = resultado['estatisticas']['notas_parciais'] + resultado['estatisticas']['notas_semestrais']
        resultado['sucesso'] = True
        resultado['resumo'] = (
            f"{resultado['estatisticas']['turmas']} turmas, "
            f"{resultado['estatisticas']['alunos']} alunos, "
            f"{resultado['estatisticas']['alunos_internos']} internos, "
            f"{resultado['estatisticas']['disciplinas']} disciplinas, "
            f"{total_notas} notas ({resultado['estatisticas']['notas_parciais']} parciais, {resultado['estatisticas']['notas_semestrais']} semestrais)"
        )
        
    except Exception as e:
        db.session.rollback()
        resultado['erro'] = str(e)
        import traceback
        traceback.print_exc()
    
    return resultado

# Rotas de Conselho de Classe
@app.route('/conselhos')
@login_required
def listar_conselhos():
    """Lista todos os conselhos com filtros"""
    page = request.args.get('page', 1, type=int)
    ano = request.args.get('ano', type=int)
    turma_id = request.args.get('turma', type=int)
    tipo = request.args.get('tipo', '')
    
    query = Conselho.query
    
    if ano:
        query = query.filter_by(ano=ano)
    if turma_id:
        query = query.filter_by(turma_id=turma_id)
    if tipo:
        query = query.filter_by(tipo=tipo)
    
    conselhos = query.order_by(Conselho.created_at.desc()).paginate(page=page, per_page=10)
    
    # Lista de anos disponíveis (últimos 5 anos)
    anos_disponiveis = list(range(datetime.now().year - 2, datetime.now().year + 3))
    
    # Tipos de conselho
    tipos_conselho = [
        ('parcial1', 'Conselho Parcial 1'),
        ('semestral1', 'Conselho Semestral 1'),
        ('parcial2', 'Conselho Parcial 2'),
        ('semestral2', 'Conselho Semestral 2')
    ]
    
    turmas = Turma.query.all()
    
    return render_template('conselhos/listar.html',
                         conselhos=conselhos,
                         anos_disponiveis=anos_disponiveis,
                         tipos_conselho=tipos_conselho,
                         turmas=turmas,
                         pode_criar=current_user.pode_criar_conselho())

@app.route('/conselhos/novo', methods=['GET', 'POST'])
@login_required
def novo_conselho():
    # Verifica permissão para criar conselho
    if not current_user.pode_criar_conselho():
        flash('Você não tem permissão para criar conselhos de classe. Apenas administradores, direção e equipe pedagógica podem criar conselhos.', 'danger')
        return redirect(url_for('listar_conselhos'))
    
    if request.method == 'POST':
        turma_id = request.form['turma_id']
        ano = int(request.form['ano'])
        semestre = int(request.form['semestre'])
        tipo = request.form['tipo']
        
        # Validação: semestre deve ser 1 para tipos parciais1/semestral1 e 2 para parciais2/semestral2
        if (tipo in ['parcial1', 'semestral1'] and semestre != 1) or \
           (tipo in ['parcial2', 'semestral2'] and semestre != 2):
            flash('Semestre incompatível com o tipo de conselho', 'danger')
            return redirect(url_for('novo_conselho'))
        
        # Verifica se já existe conselho para esta combinação
        existe = Conselho.query.filter_by(
            turma_id=turma_id,
            ano=ano,
            semestre=semestre,
            tipo=tipo,
            status='aberto'
        ).first()
        
        if existe:
            flash('Já existe um conselho aberto para esta turma/período!', 'warning')
            return redirect(url_for('listar_conselhos'))
        
        conselho = Conselho(
            turma_id=turma_id,
            ano=ano,
            semestre=semestre,
            tipo=tipo,
            created_by=current_user.id
        )
        db.session.add(conselho)
        db.session.commit()
        
        flash('Conselho criado com sucesso!', 'success')
        return redirect(url_for('ver_conselho', id=conselho.id))
    
    turmas = Turma.query.all()
    anos = list(range(datetime.now().year - 2, datetime.now().year + 3))
    
    # Tipos de conselho com descrição
    tipos_conselho = [
        {'id': 'parcial1', 'nome': 'Conselho Parcial 1', 'semestre': 1, 'icone': 'file-alt', 'cor': '#17a2b8'},
        {'id': 'semestral1', 'nome': 'Conselho Semestral 1', 'semestre': 1, 'icone': 'calendar-alt', 'cor': '#007bff'},
        {'id': 'parcial2', 'nome': 'Conselho Parcial 2', 'semestre': 2, 'icone': 'file-alt', 'cor': '#6f42c1'},
        {'id': 'semestral2', 'nome': 'Conselho Semestral 2', 'semestre': 2, 'icone': 'calendar-check', 'cor': '#28a745'},
    ]
    
    now = datetime.now()
    
    return render_template('conselhos/novo.html', 
                         turmas=turmas, 
                         anos=anos, 
                         tipos_conselho=tipos_conselho,
                         now=now)

@app.route('/conselhos/<int:id>')
@login_required
def ver_conselho(id):
    conselho = Conselho.query.get_or_404(id)
    
    campo_nota = {
        'parcial1': Nota.nota_parcial1,
        'semestral1': Nota.nota_sem1,
        'parcial2': Nota.nota_parcial2,
        'semestral2': Nota.nota_sem2
    }.get(conselho.tipo)
    
    if not campo_nota:
        flash('Tipo de conselho inválido', 'danger')
        return redirect(url_for('listar_conselhos'))
    
    campo_ordenacao = {
        'parcial1': 'nota_parcial1',
        'semestral1': 'nota_sem1',
        'parcial2': 'nota_parcial2',
        'semestral2': 'nota_sem2'
    }.get(conselho.tipo)
    
    # Verifica permissão de edição
    pode_editar = current_user.pode_editar_conselho(conselho)
    
    alunos = Aluno.query.filter_by(turma_id=conselho.turma_id, situacao='ativo').all()
    
    alunos_conselho = []
    alunos_apenas_conselho = []
    
    # Configuração das colunas baseada no tipo do conselho
    colunas_notas = {
        'parcial1': {
            'titulo': 'Nota Parcial 1',
            'campos': ['nota_parcial1'],
            'labels': ['P1'],
            'campo_principal': 'nota_parcial1'
        },
        'semestral1': {
            'titulo': 'Notas - 1º Semestre',
            'campos': ['nota_parcial1', 'nota_sem1'],
            'labels': ['P1', 'S1'],
            'campo_principal': 'nota_sem1'
        },
        'parcial2': {
            'titulo': 'Nota Parcial 2',
            'campos': ['nota_parcial1', 'nota_sem1', 'nota_parcial2'],
            'labels': ['P1', 'S1', 'P2'],
            'campo_principal': 'nota_parcial2'
        },
        'semestral2': {
            'titulo': 'Notas - Ano Letivo',
            'campos': ['nota_parcial1', 'nota_sem1', 'nota_parcial2', 'nota_sem2'],
            'labels': ['P1', 'S1', 'P2', 'S2'],
            'campo_principal': 'nota_sem2'
        }
    }
    
    config_colunas = colunas_notas.get(conselho.tipo, colunas_notas['parcial1'])
    campo_principal = config_colunas['campo_principal']
    
    for aluno in alunos:
        conselho_aluno = ConselhoAluno.query.filter_by(
            conselho_id=conselho.id,
            aluno_id=aluno.id
        ).first()
        
        if not conselho_aluno:
            conselho_aluno = ConselhoAluno(
                conselho_id=conselho.id,
                aluno_id=aluno.id,
                status='pendente'
            )
            db.session.add(conselho_aluno)
            db.session.commit()
        
        notas = db.session.query(
            Disciplina, Nota, TurmaDisciplina
        ).join(
            TurmaDisciplina, TurmaDisciplina.disciplina_id == Disciplina.id
        ).join(
            Nota, Nota.turma_disciplina_id == TurmaDisciplina.id
        ).filter(
            Nota.aluno_id == aluno.id,
            TurmaDisciplina.ano == conselho.ano,
            TurmaDisciplina.semestre == conselho.semestre
        ).all()
        
        disciplinas_notas = []
        disciplinas_abaixo = []
        disciplinas_acima = []
        tem_nota_baixa = False
        
        for disciplina, nota, td in notas:
            notas_coletadas = {}
            todas_notas_validas = []
            
            for campo in config_colunas['campos']:
                valor = getattr(nota, campo, None)
                if valor is not None:
                    notas_coletadas[campo] = float(valor)
                    todas_notas_validas.append(float(valor))
            
            nota_principal = getattr(nota, campo_principal, None)
            if nota_principal is not None:
                nota_principal = float(nota_principal)
            
            abaixo_media = nota_principal is not None and nota_principal < 7.0
            
            if abaixo_media:
                tem_nota_baixa = True
            
            media = sum(todas_notas_validas) / len(todas_notas_validas) if todas_notas_validas else None
            
            disciplina_info = {
                'disciplina': disciplina.nome,
                'codigo': disciplina.codigo,
                'notas': notas_coletadas,
                'nota_principal': nota_principal,
                'media': media,
                'abaixo_media': abaixo_media,
                'todas_notas': todas_notas_validas
            }
            
            if abaixo_media:
                disciplinas_abaixo.append(disciplina_info)
            else:
                disciplinas_acima.append(disciplina_info)
        
        disciplinas_abaixo.sort(key=lambda x: x['nota_principal'] if x['nota_principal'] is not None else 999)
        disciplinas_acima.sort(key=lambda x: x['disciplina'])
        
        disciplinas_notas = disciplinas_abaixo + disciplinas_acima
        
        data_inicio_periodo = datetime(conselho.ano, 1, 1)
        if conselho.semestre == 2:
            data_inicio_periodo = datetime(conselho.ano, 7, 1)
        
        ocorrencias_obj = Ocorrencia.query.filter_by(
            aluno_id=aluno.id
        ).filter(
            Ocorrencia.data_abertura >= data_inicio_periodo
        ).order_by(
            Ocorrencia.data_abertura.desc()
        ).limit(10).all()
        
        ocorrencias = []
        for o in ocorrencias_obj:
            ocorrencia_dict = {
                'id': o.id,
                'titulo': o.titulo,
                'descricao': o.descricao,
                'data_abertura': o.data_abertura.strftime('%Y-%m-%d %H:%M:%S') if o.data_abertura else None,
                'status': o.status,
                'prioridade': o.prioridade,
                'tipo': {
                    'nome': o.tipo.nome if o.tipo else '',
                    'cor': o.tipo.cor if o.tipo else '#6c757d'
                }
            }
            ocorrencias.append(ocorrencia_dict)

        ocorrencias_selecionadas = []
        if conselho_aluno.ocorrencias_selecionadas:
            try:
                ocorrencias_selecionadas = json.loads(conselho_aluno.ocorrencias_selecionadas)
            except:
                ocorrencias_selecionadas = []
        
        aluno_data = {
            'id': aluno.id,
            'nome': aluno.nome,
            'matricula': aluno.matricula,
            'foto': aluno.foto,
            'interno': aluno.interno,        
            'quarto': aluno.quarto,          
            'status': conselho_aluno.status if conselho_aluno.status else 'pendente',
            'parecer': conselho_aluno.parecer or '',
            'encaminhamentos': conselho_aluno.encaminhamentos or '',
            'disciplinas_notas': disciplinas_notas,
            'tem_nota_baixa': tem_nota_baixa,
            'ocorrencias': ocorrencias,
            'ocorrencias_selecionadas': ocorrencias_selecionadas,
            'config_notas': {
                'titulo': config_colunas['titulo'],
                'labels': config_colunas['labels'],
                'campos': config_colunas['campos'],
                'campo_principal': campo_principal
            }
        }
        
        alunos_conselho.append(aluno_data)
        
        if tem_nota_baixa or conselho_aluno.status != 'pendente':
            alunos_apenas_conselho.append(aluno_data)
    

    def get_pior_nota_aluno(aluno):
        pior_nota = 10.0
        for disc in aluno['disciplinas_notas']:
            if disc['nota_principal'] is not None and disc['nota_principal'] < pior_nota:
                pior_nota = disc['nota_principal']
        return pior_nota if pior_nota < 10.0 else 10.0
    
    alunos_apenas_conselho.sort(key=lambda x: (not x['tem_nota_baixa'], get_pior_nota_aluno(x), x['nome']))
    
    total_alunos = len(alunos)
    alunos_com_nota_baixa = sum(1 for a in alunos_conselho if a['tem_nota_baixa'])
    alunos_discutidos = sum(1 for a in alunos_conselho if a['status'] != 'pendente')

    alunos_alfabeticos = sorted(alunos_apenas_conselho, key=lambda x: x['nome'])

    indice_thumbnail_para_slide = {}
    for i, aluno_alf in enumerate(alunos_alfabeticos):
        for j, aluno_slide in enumerate(alunos_apenas_conselho):
            if aluno_alf['id'] == aluno_slide['id']:
                indice_thumbnail_para_slide[i] = j
                break

    return render_template('conselhos/ver.html',
                        conselho=conselho,
                        alunos=alunos_apenas_conselho,
                        alunos_thumbnails=alunos_alfabeticos,
                        mapa_indices=indice_thumbnail_para_slide,
                        total_alunos=total_alunos,
                        alunos_com_nota_baixa=alunos_com_nota_baixa,
                        alunos_decididos=alunos_discutidos,
                        pode_editar=pode_editar,
                        consideracoes_iniciais=conselho.consideracoes_iniciais or '',
                        role=current_user.role)

@app.route('/conselhos/<int:id>/consideracoes', methods=['POST'])
@login_required
def salvar_consideracoes_conselho(id):
    conselho = Conselho.query.get_or_404(id)
    
    if not current_user.pode_editar_conselho(conselho):
        return jsonify({'success': False, 'message': 'Sem permissão para editar'}), 403
    
    if request.is_json:
        dados = request.get_json()
        conselho.consideracoes_iniciais = dados.get('consideracoes', '')
    else:
        conselho.consideracoes_iniciais = request.form.get('consideracoes', '')
    
    db.session.commit()
    
    if request.is_json:
        return jsonify({'success': True, 'message': 'Considerações salvas com sucesso!'})
    else:
        flash('Considerações salvas com sucesso!', 'success')
        return redirect(url_for('ver_conselho', id=id))

@app.route('/conselhos/<int:id>/aluno/<int:aluno_id>/atualizar', methods=['POST'])
@login_required
def atualizar_aluno_conselho(id, aluno_id):
    conselho = Conselho.query.get_or_404(id)
    
    if not current_user.pode_editar_conselho(conselho):
        if request.is_json:
            return jsonify({'success': False, 'message': 'Sem permissão para editar este conselho'}), 403
        else:
            flash('Você não tem permissão para editar este conselho.', 'danger')
            return redirect(url_for('ver_conselho', id=id))
    
    conselho_aluno = ConselhoAluno.query.filter_by(
        conselho_id=id,
        aluno_id=aluno_id
    ).first_or_404()
    
    if request.is_json:
        dados = request.get_json()
        print(f"Dados recebidos para aluno {aluno_id}: {dados}")
        
        conselho_aluno.status = dados.get('status', conselho_aluno.status)
        conselho_aluno.parecer = dados.get('parecer', conselho_aluno.parecer)
        conselho_aluno.encaminhamentos = dados.get('encaminhamentos', conselho_aluno.encaminhamentos)
        
        ocorrencias_selecionadas = dados.get('ocorrencias_selecionadas', [])
        print(f"Ocorrências selecionadas para aluno {aluno_id}: {ocorrencias_selecionadas}")
        
        # Converte para JSON string
        conselho_aluno.ocorrencias_selecionadas = json.dumps(ocorrencias_selecionadas)
        print(f"JSON salvo: {conselho_aluno.ocorrencias_selecionadas}")
    else:
        conselho_aluno.status = request.form.get('status', conselho_aluno.status)
        conselho_aluno.parecer = request.form.get('parecer', conselho_aluno.parecer)
        conselho_aluno.encaminhamentos = request.form.get('encaminhamentos', conselho_aluno.encaminhamentos)
        
        ocorrencias_selecionadas = request.form.getlist('ocorrencias_selecionadas')
        conselho_aluno.ocorrencias_selecionadas = json.dumps(ocorrencias_selecionadas)
    
    db.session.commit()
    
    # Verificar se salvou corretamente
    print(f"Após commit, campo no banco: {conselho_aluno.ocorrencias_selecionadas}")
    
    if request.is_json:
        return jsonify({'success': True, 'message': 'Dados atualizados com sucesso', 'status': conselho_aluno.status})
    else:
        flash('Dados do aluno atualizados com sucesso!', 'success')
        return redirect(url_for('ver_conselho', id=id))

@app.route('/conselhos/<int:id>/finalizar', methods=['POST'])
@login_required
def finalizar_conselho(id):
    conselho = Conselho.query.get_or_404(id)
    
    # Verifica permissão de edição
    if not current_user.pode_editar_conselho(conselho):
        if request.is_json:
            return jsonify({'success': False, 'message': 'Sem permissão para finalizar este conselho'}), 403
        else:
            flash('Você não tem permissão para finalizar este conselho.', 'danger')
            return redirect(url_for('ver_conselho', id=id))
    
    # Verifica se os dados vieram como JSON ou form
    if request.is_json:
        dados = request.get_json()
        conselho.observacoes_gerais = dados.get('observacoes_gerais', '')
    else:
        conselho.observacoes_gerais = request.form.get('observacoes_gerais', '')
    
    conselho.status = 'finalizado'
    conselho.data_fim = datetime.utcnow()
    
    # Gera a ata do conselho
    ata = gerar_ata_conselho(conselho)
    conselho.ata = ata
    
    db.session.commit()
    
    if request.is_json:
        return jsonify({
            'success': True, 
            'message': 'Conselho finalizado com sucesso',
            'ata': ata
        })
    else:
        flash('Conselho finalizado com sucesso!', 'success')
        return redirect(url_for('ver_conselho', id=id))

def gerar_ata_conselho(conselho):
    """Gera um texto formatado com as decisões do conselho"""
    
    # Busca todos os alunos que estavam em conselho
    alunos_conselho = ConselhoAluno.query.filter_by(
        conselho_id=conselho.id
    ).all()
    
    ata = []
    ata.append("=" * 80)
    ata.append(f"ATA DO CONSELHO DE CLASSE")
    ata.append("=" * 80)
    ata.append(f"")
    ata.append(f"Turma: {conselho.turma.nome}")
    ata.append(f"Data: {conselho.data_fim.strftime('%d/%m/%Y %H:%M') if conselho.data_fim else conselho.data_inicio.strftime('%d/%m/%Y %H:%M')}")
    ata.append(f"Tipo: {conselho.tipo} - {conselho.semestre}° Semestre/{conselho.ano}")
    ata.append(f"")
    
    # CONSIDERAÇÕES INICIAIS
    if conselho.consideracoes_iniciais:
        ata.append("-" * 80)
        ata.append(f"CONSIDERAÇÕES INICIAIS")
        ata.append("-" * 80)
        ata.append(f"")
        ata.append(conselho.consideracoes_iniciais)
        ata.append(f"")
    
    ata.append("-" * 80)
    ata.append(f"RELATÓRIO DO CONSELHO")
    ata.append("-" * 80)
    ata.append(f"")
    
    # Separa alunos por status
    aprovados = []
    reprovados = []
    pendentes = []
    
    for ca in alunos_conselho:
        aluno = Aluno.query.get(ca.aluno_id)
        if ca.status == 'aprovado':
            aprovados.append((ca, aluno))
        elif ca.status == 'reprovado':
            reprovados.append((ca, aluno))
        else:
            pendentes.append((ca, aluno))
    
    # ALUNOS APROVADOS
    if aprovados:
        ata.append(f"✅ ALUNOS APROVADOS EM CONSELHO:")
        ata.append(f"")
        for ca, aluno in aprovados:
            ata.append(f"• {aluno.nome} (Matrícula: {aluno.matricula})")
            ata.append(f"  Decisão: APROVADO")
            if ca.parecer:
                ata.append(f"  Parecer: {ca.parecer}")
            if ca.encaminhamentos:
                ata.append(f"  Encaminhamentos: {ca.encaminhamentos}")
            
            # Ocorrências selecionadas
            if ca.ocorrencias_selecionadas:
                try:
                    ocorrencias_ids = json.loads(ca.ocorrencias_selecionadas)
                    if ocorrencias_ids and len(ocorrencias_ids) > 0:
                        ata.append(f"  Ocorrências relacionadas:")
                        for o_id in ocorrencias_ids:
                            ocorrencia = Ocorrencia.query.get(o_id)
                            if ocorrencia:
                                ata.append(f"    • #{ocorrencia.id} - {ocorrencia.titulo}")
                except:
                    pass
            ata.append(f"")
    
    # ALUNOS REPROVADOS
    if reprovados:
        ata.append(f"❌ ALUNOS REPROVADOS EM CONSELHO:")
        ata.append(f"")
        for ca, aluno in reprovados:
            ata.append(f"• {aluno.nome} (Matrícula: {aluno.matricula})")
            ata.append(f"  Decisão: REPROVADO")
            if ca.parecer:
                ata.append(f"  Parecer: {ca.parecer}")
            if ca.encaminhamentos:
                ata.append(f"  Encaminhamentos: {ca.encaminhamentos}")
            
            # Ocorrências selecionadas
            if ca.ocorrencias_selecionadas:
                try:
                    ocorrencias_ids = json.loads(ca.ocorrencias_selecionadas)
                    if ocorrencias_ids and len(ocorrencias_ids) > 0:
                        ata.append(f"  Ocorrências relacionadas:")
                        for o_id in ocorrencias_ids:
                            ocorrencia = Ocorrencia.query.get(o_id)
                            if ocorrencia:
                                ata.append(f"    • #{ocorrencia.id} - {ocorrencia.titulo}")
                except:
                    pass
            ata.append(f"")
    
    # ALUNOS PENDENTES (discutidos mas sem decisão final)
    if pendentes:
        ata.append(f"⏳ ALUNOS PENDENTES (discutidos - aguardando deliberação):")
        ata.append(f"")
        for ca, aluno in pendentes:
            ata.append(f"• {aluno.nome} (Matrícula: {aluno.matricula})")
            ata.append(f"  Status: PENDENTE")
            if ca.parecer:
                ata.append(f"  Parecer: {ca.parecer}")
            if ca.encaminhamentos:
                ata.append(f"  Encaminhamentos: {ca.encaminhamentos}")
            
            # Ocorrências selecionadas
            if ca.ocorrencias_selecionadas:
                try:
                    ocorrencias_ids = json.loads(ca.ocorrencias_selecionadas)
                    if ocorrencias_ids and len(ocorrencias_ids) > 0:
                        ata.append(f"  Ocorrências relacionadas:")
                        for o_id in ocorrencias_ids:
                            ocorrencia = Ocorrencia.query.get(o_id)
                            if ocorrencia:
                                ata.append(f"    • #{ocorrencia.id} - {ocorrencia.titulo}")
                except:
                    pass
            ata.append(f"")
    
    # OBSERVAÇÕES GERAIS
    if conselho.observacoes_gerais:
        ata.append(f"")
        ata.append(f"📝 OBSERVAÇÕES GERAIS:")
        ata.append(f"{conselho.observacoes_gerais}")
        ata.append(f"")
    
    # RODAPÉ
    ata.append("=" * 80)
    ata.append(f"Documento gerado pelo SIGEC - Sistema de Gestão de Conselhos de Classe")
    ata.append(f"IF Farroupilha - Campus Frederico Westphalen")
    ata.append(f"Gerado em: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}")
    ata.append("=" * 80)
    
    return "\n".join(ata)

@app.route('/conselhos/<int:id>/ata')
@login_required
def ver_ata_conselho(id):
    conselho = Conselho.query.get_or_404(id)
    
    # Se a ata ainda não foi gerada (por exemplo, conselho não finalizado)
    if not conselho.ata:
        if conselho.status == 'finalizado':
            # Gera a ata agora
            conselho.ata = gerar_ata_conselho(conselho)
            db.session.commit()
        else:
            flash('A ata só está disponível após a finalização do conselho.', 'warning')
            return redirect(url_for('ver_conselho', id=id))
    
    return render_template('conselhos/ata.html', conselho=conselho, ata=conselho.ata)

@app.route('/conselhos/<int:id>/ata/download')
@login_required
def download_ata_conselho(id):
    conselho = Conselho.query.get_or_404(id)
    
    if not conselho.ata and conselho.status == 'finalizado':
        conselho.ata = gerar_ata_conselho(conselho)
        db.session.commit()
    
    if not conselho.ata:
        flash('Ata não disponível.', 'danger')
        return redirect(url_for('ver_conselho', id=id))
    
    # Cria arquivo para download
    buffer = BytesIO()
    buffer.write(conselho.ata.encode('utf-8'))
    buffer.seek(0)
    
    nome_arquivo = f"ata_conselho_{conselho.turma.nome}_{conselho.data_fim.strftime('%Y%m%d')}.txt"
    
    return send_file(
        buffer,
        mimetype='text/plain',
        as_attachment=True,
        download_name=nome_arquivo
    )

@app.route('/conselhos/<int:id>/reabrir', methods=['GET', 'POST'])
@login_required
def reabrir_conselho(id):
    conselho = Conselho.query.get_or_404(id)
    
    if not current_user.pode_editar_conselho(conselho):
        flash('Você não tem permissão para reabrir este conselho!', 'danger')
        return redirect(url_for('ver_conselho', id=id))
    
    if conselho.status != 'finalizado':
        flash('Apenas conselhos finalizados podem ser reabertos!', 'warning')
        return redirect(url_for('ver_conselho', id=id))
    
    if request.method == 'POST':
        motivo = request.form.get('motivo')
        
        if not motivo:
            flash('Informe o motivo da reabertura!', 'danger')
            return redirect(url_for('reabrir_conselho', id=id))
        
        versao_antiga = conselho.arquivar_versao_atual(motivo, current_user.id)
        db.session.commit()
        
        flash(f'Conselho reaberto com sucesso! Nova versão: {conselho.versao_atual}', 'success')
        flash('Todas as informações da versão anterior foram mantidas e podem ser editadas.', 'info')
        return redirect(url_for('ver_conselho', id=id))
    
    return render_template('conselhos/reabrir.html', conselho=conselho)

@app.route('/api/modelos-encaminhamentos')
@login_required
def get_modelos_encaminhamentos():
    modelos = ModeloEncaminhamento.query.filter_by(ativo=True).order_by(ModeloEncaminhamento.titulo).all()
    
    modelos_json = []
    for m in modelos:
        modelos_json.append({
            'id': m.id,
            'titulo': m.titulo,
            'texto': m.texto,
            'categoria': m.categoria
        })
    
    return jsonify(modelos_json)

@app.route('/conselhos/<int:id>/versoes')
@login_required
def ver_versoes_conselho(id):
    conselho = Conselho.query.get_or_404(id)
    versoes = conselho.historico_versoes.order_by(ConselhoVersao.versao.desc()).all()
    
    return render_template('conselhos/versoes.html', 
                         conselho=conselho, 
                         versoes=versoes)

@app.route('/conselhos/versao/<int:versao_id>')
@login_required
def ver_versao_conselho(versao_id):
    from models import ConselhoVersao, Aluno
    
    versao = ConselhoVersao.query.get_or_404(versao_id)
    conselho = versao.conselho
    
    # Busca os alunos desta versão
    alunos_versao = []
    for av in versao.alunos:
        aluno = Aluno.query.get(av.aluno_id)
        if aluno:
            alunos_versao.append({
                'id': aluno.id,
                'nome': aluno.nome,
                'matricula': aluno.matricula,
                'status': av.status,
                'parecer': av.parecer,
                'encaminhamentos': av.encaminhamentos
            })
    
    return render_template('conselhos/ver_versao.html',
                         conselho=conselho,
                         versao=versao,
                         alunos=alunos_versao)

@app.route('/conselhos/<int:id>/versao/<int:versao>')
@login_required
def ver_conselho_versao(id, versao):
    from models import ConselhoVersao
    
    conselho = Conselho.query.get_or_404(id)
    versao_obj = conselho.historico_versoes.filter_by(versao=versao).first_or_404()
    
    # Redireciona para a rota de visualização de versão
    return redirect(url_for('ver_versao_conselho', versao_id=versao_obj.id))


# Rotas para Calendário
@app.route('/api/calendario/eventos')
@login_required
def listar_eventos():
    """Retorna eventos do calendário"""
    try:
        eventos = CalendarioEvento.query.order_by(CalendarioEvento.data_inicio).all()
        
        eventos_json = []
        for e in eventos:
            eventos_json.append({
                'id': e.id,
                'title': e.titulo,
                'start': e.data_inicio.strftime('%Y-%m-%d %H:%M:%S'),
                'end': e.data_fim.strftime('%Y-%m-%d %H:%M:%S') if e.data_fim else None,
                'color': e.cor,
                'tipo': e.tipo,
                'turma': e.turma.nome if e.turma else None
            })
        
        return jsonify(eventos_json)
    except Exception as e:
        print(f"Erro ao listar eventos: {e}")
        return jsonify([])

@app.route('/calendario/evento/novo', methods=['POST'])
@login_required
def novo_evento():
    """Cria um novo evento no calendário (apenas admin/direcao)"""
    if not current_user.role in ['admin', 'direcao']:
        flash('Permissão negada', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        evento = CalendarioEvento(
            titulo=request.form['titulo'],
            descricao=request.form.get('descricao', ''),
            data_inicio=datetime.strptime(request.form['data_inicio'], '%Y-%m-%dT%H:%M'),
            data_fim=datetime.strptime(request.form['data_fim'], '%Y-%m-%dT%H:%M') if request.form.get('data_fim') else None,
            tipo=request.form['tipo'],
            turma_id=request.form.get('turma_id') if request.form.get('turma_id') else None,
            cor=request.form.get('cor', '#00420C'),
            created_by=current_user.id
        )
        
        db.session.add(evento)
        db.session.commit()
        
        flash('Evento criado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao criar evento: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

# Rota para limpar eventos antigos
@app.route('/api/calendario/limpar', methods=['POST'])
@login_required
def limpar_eventos_antigos():
    """Remove eventos com data passada"""
    if not current_user.role in ['admin', 'direcao']:
        return jsonify({'success': False, 'message': 'Permissão negada'}), 403
    
    try:
        hoje = datetime.now()
        eventos_antigos = CalendarioEvento.query.filter(
            CalendarioEvento.data_fim < hoje
        ).all()
        
        quantidade = len(eventos_antigos)
        
        for evento in eventos_antigos:
            db.session.delete(evento)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{quantidade} evento(s) antigo(s) removido(s)',
            'quantidade': quantidade
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/avisos/limpar', methods=['POST'])
@login_required
def limpar_avisos():
    """Remove todos os avisos (ou apenas os não fixados)"""
    if not current_user.role in ['admin', 'direcao']:
        return jsonify({'success': False, 'message': 'Permissão negada'}), 403
    
    try:
        avisos_remover = Aviso.query.filter_by(fixado=False).all()
        
        quantidade = len(avisos_remover)
        
        for aviso in avisos_remover:
            db.session.delete(aviso)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{quantidade} aviso(s) removido(s)',
            'quantidade': quantidade
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Rotas para Avisos
@app.route('/api/avisos')
@login_required
def listar_avisos():
    """Retorna avisos do sistema"""
    try:
        avisos = Aviso.query.order_by(
            Aviso.fixado.desc(), 
            Aviso.created_at.desc()
        ).limit(10).all()
        
        avisos_json = []
        for a in avisos:
            avisos_json.append({
                'id': a.id,
                'titulo': a.titulo,
                'conteudo': a.conteudo,
                'tipo': a.tipo,
                'importante': a.importante,
                'fixado': a.fixado,
                'criador': a.criador.nome if a.criador else 'Sistema',
                'criado_em': a.created_at.strftime('%d/%m/%Y %H:%M') if a.created_at else ''
            })
        
        return jsonify(avisos_json)
    except Exception as e:
        print(f"Erro ao listar avisos: {e}")
        return jsonify([])

@app.route('/avisos/novo', methods=['POST'])
@login_required
def novo_aviso():
    """Cria um novo aviso (apenas admin/direcao)"""
    if not current_user.role in ['admin', 'direcao']:
        flash('Permissão negada', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        aviso = Aviso(
            titulo=request.form['titulo'],
            conteudo=request.form['conteudo'],
            tipo=request.form.get('tipo', 'geral'),
            importante='importante' in request.form,
            fixado='fixado' in request.form,
            created_by=current_user.id
        )
        
        db.session.add(aviso)
        db.session.commit()
        
        flash('Aviso criado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao criar aviso: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

# Rotas de relatórios
@app.route('/relatorios', methods=['GET', 'POST'])
@login_required
def relatorios():
    if request.method == 'POST':
        tipo_relatorio = request.form['tipo']
        data_inicio = datetime.strptime(request.form['data_inicio'], '%Y-%m-%d') if request.form['data_inicio'] else None
        data_fim = datetime.strptime(request.form['data_fim'], '%Y-%m-%d') if request.form['data_fim'] else None
        formato = request.form['formato']
        
        if tipo_relatorio == 'ocorrencias':
            return gerar_relatorio_ocorrencias(data_inicio, data_fim, formato)
        elif tipo_relatorio == 'alunos':
            return gerar_relatorio_alunos(formato)
        elif tipo_relatorio == 'estatisticas':
            return gerar_relatorio_estatisticas(data_inicio, data_fim, formato)
    
    return render_template('relatorios/gerar.html')

def gerar_relatorio_ocorrencias(data_inicio, data_fim, formato):
    query = Ocorrencia.query
    
    if data_inicio:
        query = query.filter(Ocorrencia.data_abertura >= data_inicio)
    if data_fim:
        query = query.filter(Ocorrencia.data_abertura <= data_fim)
    
    ocorrencias = query.all()
    
    dados = []
    for o in ocorrencias:
        dados.append({
            'ID': o.id,
            'Título': o.titulo,
            'Aluno': o.aluno.nome if o.aluno else '',
            'Tipo': o.tipo.nome if o.tipo else '',
            'Status': o.status,
            'Prioridade': o.prioridade,
            'Data Abertura': o.data_abertura.strftime('%d/%m/%Y %H:%M'),
            'Setor Origem': o.setor_origem.nome if o.setor_origem else '',
            'Setor Destino': o.setor_destino.nome if o.setor_destino else '',
            'Criador': o.criador.nome if o.criador else ''
        })
    
    return exportar_relatorio(dados, 'relatorio_ocorrencias', formato)

def gerar_relatorio_alunos(formato):
    alunos = Aluno.query.all()
    
    dados = []
    for a in alunos:
        dados.append({
            'Nome': a.nome,
            'Matrícula': a.matricula,
            'Turma': a.turma.nome if a.turma else '',
            'Situação': a.situacao,
            'Email': a.email,
            'Telefone': a.telefone,
            'Total Ocorrências': len(a.ocorrencias)
        })
    
    return exportar_relatorio(dados, 'relatorio_alunos', formato)

def gerar_relatorio_estatisticas(data_inicio, data_fim, formato):
    # Estatísticas gerais
    total_alunos = Aluno.query.count()
    alunos_ativos = Aluno.query.filter_by(situacao='ativo').count()
    
    total_ocorrencias = Ocorrencia.query.count()
    if data_inicio and data_fim:
        ocorrencias_periodo = Ocorrencia.query.filter(
            Ocorrencia.data_abertura.between(data_inicio, data_fim)
        ).count()
    else:
        ocorrencias_periodo = total_ocorrencias
    
    # Por setor
    ocorrencias_por_setor = db.session.query(
        Setor.nome, db.func.count(Ocorrencia.id)
    ).join(Ocorrencia, Setor.id == Ocorrencia.setor_destino_id)\
     .group_by(Setor.id).all()
    
    # Por status
    ocorrencias_por_status = db.session.query(
        Ocorrencia.status, db.func.count(Ocorrencia.id)
    ).group_by(Ocorrencia.status).all()
    
    # Por tipo
    ocorrencias_por_tipo = db.session.query(
        TipoOcorrencia.nome, db.func.count(Ocorrencia.id)
    ).join(Ocorrencia, TipoOcorrencia.id == Ocorrencia.tipo_id)\
     .group_by(TipoOcorrencia.id).all()
    
    dados = {
        'Total de Alunos': total_alunos,
        'Alunos Ativos': alunos_ativos,
        'Total de Ocorrências': total_ocorrencias,
        'Ocorrências no Período': ocorrencias_periodo,
        'Ocorrências por Setor': dict(ocorrencias_por_setor),
        'Ocorrências por Status': dict(ocorrencias_por_status),
        'Ocorrências por Tipo': dict(ocorrencias_por_tipo)
    }
    
    if formato == 'pdf':
        return gerar_pdf_estatisticas(dados)
    elif formato == 'excel':
        # Converte para formato tabular para Excel
        dados_tabela = []
        for setor, count in ocorrencias_por_setor:
            dados_tabela.append({'Setor': setor, 'Quantidade': count, 'Tipo': 'Por Setor'})
        for status, count in ocorrencias_por_status:
            dados_tabela.append({'Setor': status, 'Quantidade': count, 'Tipo': 'Por Status'})
        for tipo, count in ocorrencias_por_tipo:
            dados_tabela.append({'Setor': tipo, 'Quantidade': count, 'Tipo': 'Por Tipo'})
        
        return exportar_relatorio(dados_tabela, 'relatorio_estatisticas', formato)

def exportar_relatorio(dados, nome_arquivo, formato):
    if formato == 'excel':
        df = pd.DataFrame(dados)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Relatório')
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'{nome_arquivo}.xlsx'
        )
    
    elif formato == 'csv':
        df = pd.DataFrame(dados)
        output = BytesIO()
        df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'{nome_arquivo}.csv'
        )
    
    elif formato == 'pdf':
        return gerar_pdf_tabela(dados, nome_arquivo)

def gerar_pdf_tabela(dados, nome_arquivo):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elementos = []
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#00420C'),
        spaceAfter=30
    )
    
    # Título
    titulo = Paragraph(f'Relatório - {nome_arquivo.replace("_", " ").title()}', title_style)
    elementos.append(titulo)
    elementos.append(Spacer(1, 0.2*inch))
    
    # Cabeçalho do IFFar
    cabecalho = Paragraph(
        'INSTITUTO FEDERAL FARROUPILHA - SISTEMA DE CONSELHO DE CLASSE',
        styles['Normal']
    )
    elementos.append(cabecalho)
    elementos.append(Spacer(1, 0.3*inch))
    
    # Data
    data = Paragraph(f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}', styles['Normal'])
    elementos.append(data)
    elementos.append(Spacer(1, 0.3*inch))
    
    if dados:
        # Converte dados para tabela
        if isinstance(dados, list) and len(dados) > 0:
            cabecalhos = list(dados[0].keys())
            dados_tabela = [cabecalhos]
            
            for item in dados:
                linha = [str(item.get(h, '')) for h in cabecalhos]
                dados_tabela.append(linha)
            
            # Cria tabela
            tabela = Table(dados_tabela)
            tabela.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00420C')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elementos.append(tabela)
    
    doc.build(elementos)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'{nome_arquivo}.pdf'
    )

def gerar_pdf_estatisticas(dados):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    elementos = []
    
    styles = getSampleStyleSheet()
    
    # Título
    titulo = Paragraph('RELATÓRIO ESTATÍSTICO - CONSELHO DE CLASSE', 
                      ParagraphStyle('Title', parent=styles['Title'], textColor=colors.HexColor('#00420C')))
    elementos.append(titulo)
    elementos.append(Spacer(1, 0.3*inch))
    
    # Informações gerais
    info_data = [
        ['Total de Alunos', str(dados['Total de Alunos'])],
        ['Alunos Ativos', str(dados['Alunos Ativos'])],
        ['Total de Ocorrências', str(dados['Total de Ocorrências'])],
        ['Ocorrências no Período', str(dados['Ocorrências no Período'])]
    ]
    
    tabela_info = Table(info_data)
    tabela_info.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00420C')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ]))
    
    elementos.append(tabela_info)
    elementos.append(Spacer(1, 0.3*inch))
    
    doc.build(elementos)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='relatorio_estatisticas.pdf'
    )

@app.route('/api/conselhos/<int:id>/aluno/<int:aluno_id>/dados')
@login_required
def api_conselho_aluno_dados(id, aluno_id):
    conselho = Conselho.query.get_or_404(id)
    conselho_aluno = ConselhoAluno.query.filter_by(
        conselho_id=id,
        aluno_id=aluno_id
    ).first_or_404()
    
    return jsonify({
        'success': True,
        'aluno': {
            'id': aluno_id,
            'status': conselho_aluno.status,
            'parecer': conselho_aluno.parecer,
            'encaminhamentos': conselho_aluno.encaminhamentos
        }
    })

# Rotas administrativas
@app.route('/admin/usuarios')
@login_required
@role_required('admin')
def admin_usuarios():
    usuarios = Usuario.query.all()
    setores = Setor.query.all()
    return render_template('admin/usuarios.html', usuarios=usuarios, setores=setores)

@app.route('/admin/usuarios/novo', methods=['POST'])
@login_required
@role_required('admin')
def admin_novo_usuario():
    # Pega a matrícula do formulário
    matricula = request.form.get('matricula', '').strip()
    
    if not matricula:
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        matricula = f"USER{timestamp}"
    
    # Verifica se já existe usuário com este email
    usuario_existente = Usuario.query.filter_by(email=request.form['email']).first()
    if usuario_existente:
        flash('Já existe um usuário com este email!', 'danger')
        return redirect(url_for('admin_usuarios'))
    
    # Verifica se já existe usuário com esta matrícula
    usuario_existente = Usuario.query.filter_by(matricula=matricula).first()
    if usuario_existente:
        flash('Já existe um usuário com esta matrícula!', 'danger')
        return redirect(url_for('admin_usuarios'))
    
    usuario = Usuario(
        nome=request.form['nome'],
        email=request.form['email'],
        matricula=matricula,
        role=request.form['role'],
        setor_id=request.form['setor_id'] if request.form['setor_id'] else None
    )
    usuario.set_senha(request.form['senha'])
    
    try:
        db.session.add(usuario)
        db.session.commit()
        flash('Usuário criado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar usuário: {str(e)}', 'danger')
    
    return redirect(url_for('admin_usuarios'))

@app.route('/admin/usuarios/<int:id>/toggle', methods=['POST'])
@login_required
@role_required('admin')
def admin_toggle_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    
    if usuario.id == current_user.id:
        return jsonify({'success': False, 'message': 'Você não pode alterar seu próprio status!'}), 400
    
    usuario.ativo = not usuario.ativo
    db.session.commit()
    
    status = 'ativado' if usuario.ativo else 'desativado'
    return jsonify({'success': True, 'message': f'Usuário {status} com sucesso!'})


@app.route('/admin/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            usuario.nome = request.form['nome']
            usuario.email = request.form['email']
            usuario.role = request.form['role']
            usuario.setor_id = request.form.get('setor_id') if request.form.get('setor_id') else None
            
            # Se a senha foi preenchida, atualiza
            nova_senha = request.form.get('senha')
            if nova_senha and nova_senha.strip():
                usuario.set_senha(nova_senha)
                flash('Senha atualizada com sucesso!', 'success')
            
            # Se o usuário está se editando, atualiza a sessão
            if usuario.id == current_user.id:
                flash('Seu perfil foi atualizado. Faça login novamente para aplicar alterações na sessão.', 'info')
            
            db.session.commit()
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('admin_usuarios'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar usuário: {str(e)}', 'danger')
            return redirect(url_for('admin_editar_usuario', id=id))
    
    setores = Setor.query.all()
    return render_template('admin/editar_usuario.html', usuario=usuario, setores=setores)


@app.route('/admin/usuarios/<int:id>/reset_senha', methods=['POST'])
@login_required
@role_required('admin')
def admin_reset_senha(id):
    """Rota rápida para resetar senha"""
    usuario = Usuario.query.get_or_404(id)
    
    nova_senha = request.form.get('nova_senha')
    if not nova_senha:
        flash('Nova senha não informada!', 'danger')
        return redirect(url_for('admin_usuarios'))
    
    usuario.set_senha(nova_senha)
    db.session.commit()
    
    flash(f'Senha de {usuario.nome} resetada com sucesso!', 'success')
    return redirect(url_for('admin_usuarios'))

@app.route('/admin/usuarios/<int:id>/excluir', methods=['POST'])
@login_required
@role_required('admin')
def admin_excluir_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    
    # Impede que o admin exclua a si mesmo
    if usuario.id == current_user.id:
        flash('Você não pode excluir seu próprio usuário!', 'danger')
        return redirect(url_for('admin_usuarios'))
    
    nome = usuario.nome
    db.session.delete(usuario)
    db.session.commit()
    
    flash(f'Usuário {nome} excluído com sucesso!', 'success')
    return redirect(url_for('admin_usuarios'))

@app.route('/api/conselhos/<int:id>/stream')
@login_required
def stream_conselho(id):
    def event_stream():
        queue = Queue()
        
        # Registra este cliente na fila do conselho
        if id not in conselho_event_queues:
            conselho_event_queues[id] = []
        conselho_event_queues[id].append(queue)
        
        try:
            while True:
                # Espera por eventos (timeout de 30 segundos para manter conexão)
                event = queue.get(timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
        except:
            # Remove cliente quando desconectar
            if id in conselho_event_queues:
                conselho_event_queues[id].remove(queue)
    
    return Response(event_stream(), mimetype="text/event-stream")

def notificar_atualizacao_conselho(conselho_id, tipo, dados):
    """Envia atualização para todos os clientes ouvindo este conselho"""
    if conselho_id in conselho_event_queues:
        for queue in conselho_event_queues[conselho_id]:
            queue.put({
                'tipo': tipo,
                'dados': dados,
                'timestamp': datetime.utcnow().isoformat()
            })

# API para estatísticas
@app.route('/api/estatisticas')
@login_required
def api_estatisticas():
    # Dados para gráficos
    ocorrencias_por_mes = db.session.query(
        db.func.strftime('%Y-%m', Ocorrencia.data_abertura).label('mes'),
        db.func.count(Ocorrencia.id).label('total')
    ).group_by('mes').order_by('mes').limit(12).all()
    
    alunos_por_turma = db.session.query(
        Turma.nome,
        db.func.count(Aluno.id)
    ).join(Aluno, Turma.id == Aluno.turma_id, isouter=True)\
     .group_by(Turma.id).all()
    
    return jsonify({
        'ocorrencias_por_mes': [{'mes': m[0], 'total': m[1]} for m in ocorrencias_por_mes],
        'alunos_por_turma': [{'turma': t[0], 'total': t[1]} for t in alunos_por_turma]
    })

def criar_admin_se_nao_existir():
    """Função simples para criar admin apenas se não existir"""
    with app.app_context():
        # CRIA AS TABELAS (se não existirem)
        db.create_all()
        print("Tabelas verificadas")
        
        # Verifica se já existe um admin
        admin = Usuario.query.filter_by(email='admin@iffar.edu.br').first()
        
        if not admin:
            admin = Usuario(
                nome='Admin',
                email='admin@iffar.edu.br',
                matricula='001',
                role='admin',
                ativo=True
            )
            admin.set_senha('123')
            db.session.add(admin)
            db.session.commit()
            
            print("="*50)
            print("ADMIN CRIADO COM SUCESSO!")
            print("Email: admin@iffar.edu.br")
            print("Senha: 123")
            print("="*50)
        else:
            print("="*50)
            print("ADMIN JÁ EXISTE!")
            print("Email: admin@iffar.edu.br")
            print("="*50)

criar_admin_se_nao_existir()

@app.route('/api/conselhos/<int:id>/estatisticas')
@login_required
def api_conselho_estatisticas(id):
    conselho = Conselho.query.get_or_404(id)
    
    # Busca todos os alunos da turma
    alunos = Aluno.query.filter_by(turma_id=conselho.turma_id, situacao='ativo').all()
    
    alunos_com_nota_baixa = 0
    alunos_decididos = 0  # Aprovados + Reprovados
    
    for aluno in alunos:
        # Busca notas do aluno
        notas = db.session.query(
            Disciplina, Nota, TurmaDisciplina
        ).join(
            TurmaDisciplina, TurmaDisciplina.disciplina_id == Disciplina.id
        ).join(
            Nota, Nota.turma_disciplina_id == TurmaDisciplina.id
        ).filter(
            Nota.aluno_id == aluno.id,
            TurmaDisciplina.ano == conselho.ano,
            TurmaDisciplina.semestre == conselho.semestre
        ).all()
        
        tem_nota_baixa = False
        for disciplina, nota, td in notas:
            if conselho.tipo == 'parcial1':
                valor_nota = nota.nota_parcial1
            elif conselho.tipo == 'semestral1':
                valor_nota = nota.nota_sem1
            elif conselho.tipo == 'parcial2':
                valor_nota = nota.nota_parcial2
            else:
                valor_nota = nota.nota_sem2
            
            if valor_nota is not None and valor_nota < 7.0:
                tem_nota_baixa = True
                break
        
        if tem_nota_baixa:
            alunos_com_nota_baixa += 1
            
            # Verifica se já foi decidido (aprovado ou reprovado)
            conselho_aluno = ConselhoAluno.query.filter_by(
                conselho_id=id,
                aluno_id=aluno.id
            ).first()
            
            if conselho_aluno and conselho_aluno.status in ['aprovado', 'reprovado']:
                alunos_decididos += 1
    
    return jsonify({
        'success': True,
        'total_alunos': len(alunos),
        'alunos_com_nota_baixa': alunos_com_nota_baixa,
        'alunos_decididos': alunos_decididos,
        'progresso': (alunos_decididos / alunos_com_nota_baixa * 100) if alunos_com_nota_baixa > 0 else 0
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Banco de dados inicializado")

        if ModeloEncaminhamento.query.count() == 0:
            from seeds import seed_modelos_encaminhamentos
            seed_modelos_encaminhamentos()
            print("Modelos de encaminhamento criados")
        
        # CRIA SETORES PADRÃO SE NÃO EXISTIREM
        if Setor.query.count() == 0:
            setores = [
                {'nome': 'Direção', 'cor': '#00420C', 'icone': 'building'},
                {'nome': 'Coordenação Pedagógica', 'cor': '#0066B3', 'icone': 'book'},
                {'nome': 'Assistência Estudantil', 'cor': '#E30613', 'icone': 'heart'},
                {'nome': 'Saúde', 'cor': '#00A859', 'icone': 'hospital'},
                {'nome': 'Apoio Pedagógico', 'cor': '#FFA500', 'icone': 'graduation-cap'},
                {'nome': 'Ensino', 'cor': '#FFA500', 'icone': 'graduation-cap'},
                {'nome': 'Secretaria', 'cor': '#800080', 'icone': 'file-text'},
                {'nome': 'Biblioteca', 'cor': '#8B4513', 'icone': 'book-open'},
            ]
            
            for s in setores:
                setor = Setor(**s)
                db.session.add(setor)
            db.session.commit()
            print("Setores criados")
        
        # CRIA TIPOS DE OCORRÊNCIA PADRÃO SE NÃO EXISTIREM
        if TipoOcorrencia.query.count() == 0:
            tipos = [
                {'nome': 'Problema de Aprendizagem', 'cor': '#FFC107', 'icone': 'book', 'prazo_dias': 7},
                {'nome': 'Problema Comportamental', 'cor': '#DC3545', 'icone': 'exclamation-triangle', 'prazo_dias': 3},
                {'nome': 'Problema de Saúde', 'cor': '#17A2B8', 'icone': 'heart', 'prazo_dias': 2},
                {'nome': 'Assistência Estudantil', 'cor': '#28A745', 'icone': 'hand-holding-heart', 'prazo_dias': 5},
                {'nome': 'Infrequência', 'cor': '#FD7E14', 'icone': 'calendar-times', 'prazo_dias': 3},
                {'nome': 'Baixo Rendimento', 'cor': '#6F42C1', 'icone': 'chart-line', 'prazo_dias': 7},
                {'nome': 'Outros', 'cor': '#6C757D', 'icone': 'ellipsis-h', 'prazo_dias': 5},
            ]
            
            for t in tipos:
                tipo = TipoOcorrencia(**t)
                db.session.add(tipo)
            db.session.commit()
            print("Tipos de ocorrência criados")
        
        # CRIA ADMIN SE NÃO EXISTIR
        criar_admin_se_nao_existir()
    
    # app.run(debug=True)
    app.run(host='0.0.0.0', port=5002, debug=True)