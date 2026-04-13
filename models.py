from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    matricula = db.Column(db.String(20), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200))
    role = db.Column(db.String(50), default='professor')
    setor_id = db.Column(db.Integer, db.ForeignKey('setores.id'))
    foto_perfil = db.Column(db.String(200))
    ativo = db.Column(db.Boolean, default=True)
    primeiro_acesso = db.Column(db.Boolean, default=True)
    ultimo_acesso = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    setor = db.relationship('Setor', backref='usuarios')
    
    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)
    
    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def pode_ver_todas_ocorrencias(self):
        return self.role in ['admin', 'direcao', 'pedagogico', 'assistente_estudantil']
    
    def pode_criar_ocorrencia(self):
        return self.role in ['admin', 'direcao', 'professor', 'assistente_estudantil', 'saude', 'pedagogico', 'coordenador', 'usuario']
    
    def pode_criar_conselho(self):
        roles_permitidas = ['admin', 'direcao', 'pedagogico']
        return self.role in roles_permitidas and self.ativo
    
    def pode_editar_conselho(self, conselho=None):
        if not self.ativo:
            return False
        if self.role == 'admin':
            return True
        if conselho and conselho.status != 'aberto':
            return False
        return self.pode_criar_conselho()
    
    def __repr__(self):
        return f'<Usuario {self.nome}>'


class Setor(db.Model):
    __tablename__ = 'setores'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    cor = db.Column(db.String(20))
    icone = db.Column(db.String(50))
    
    def __repr__(self):
        return f'<Setor {self.nome}>'


class Turma(db.Model):
    __tablename__ = 'turmas'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    curso = db.Column(db.String(100), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    turno = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    alunos = db.relationship('Aluno', back_populates='turma', lazy=True)
    conselhos = db.relationship('Conselho', back_populates='turma', lazy='dynamic')


class Disciplina(db.Model):
    __tablename__ = 'disciplinas'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    codigo = db.Column(db.String(20), unique=True)
    carga_horaria = db.Column(db.Integer)
    
    def __repr__(self):
        return f'<Disciplina {self.nome}>'


class TipoOcorrencia(db.Model):
    __tablename__ = 'tipos_ocorrencia'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    cor = db.Column(db.String(20))
    icone = db.Column(db.String(50))
    prazo_dias = db.Column(db.Integer, default=5)
    
    def __repr__(self):
        return f'<TipoOcorrencia {self.nome}>'


class CalendarioEvento(db.Model):
    __tablename__ = 'calendario_eventos'
    
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    data_inicio = db.Column(db.DateTime, nullable=False)
    data_fim = db.Column(db.DateTime)
    tipo = db.Column(db.String(50))
    turma_id = db.Column(db.Integer, db.ForeignKey('turmas.id'), nullable=True)
    cor = db.Column(db.String(20), default='#00420C')
    created_by = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    turma = db.relationship('Turma', backref='eventos')
    criador = db.relationship('Usuario', backref='eventos_criados')


class Aviso(db.Model):
    __tablename__ = 'avisos'
    
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.String(50), default='geral')
    importante = db.Column(db.Boolean, default=False)
    fixado = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    criador = db.relationship('Usuario', backref='avisos_criados')


class Aluno(db.Model):
    __tablename__ = 'alunos'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    matricula = db.Column(db.String(20), unique=True, nullable=False)
    data_nascimento = db.Column(db.Date)
    cpf = db.Column(db.String(14))
    email = db.Column(db.String(100))
    telefone = db.Column(db.String(20))
    endereco = db.Column(db.String(200))
    cidade = db.Column(db.String(100))
    uf = db.Column(db.String(2))
    interno = db.Column(db.Boolean, default=False)
    quarto = db.Column(db.String(10))
    turma_id = db.Column(db.Integer, db.ForeignKey('turmas.id'))
    foto = db.Column(db.String(200))
    situacao = db.Column(db.String(20), default='ativo')
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    turma = db.relationship('Turma', back_populates='alunos')
    ocorrencias = db.relationship('Ocorrencia', backref='aluno', lazy='dynamic')
    notas = db.relationship('Nota', backref='aluno', lazy='dynamic')
    frequencias = db.relationship('Frequencia', backref='aluno', lazy='dynamic')


class TurmaDisciplina(db.Model):
    __tablename__ = 'turmas_disciplinas'
    
    id = db.Column(db.Integer, primary_key=True)
    turma_id = db.Column(db.Integer, db.ForeignKey('turmas.id'))
    disciplina_id = db.Column(db.Integer, db.ForeignKey('disciplinas.id'))
    ano = db.Column(db.Integer)
    semestre = db.Column(db.Integer)
    
    turma = db.relationship('Turma', backref='disciplinas_ofertadas')
    disciplina = db.relationship('Disciplina', backref='turmas_ofertadas')


class Nota(db.Model):
    __tablename__ = 'notas'
    
    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'))
    turma_disciplina_id = db.Column(db.Integer, db.ForeignKey('turmas_disciplinas.id'))
    nota_parcial1 = db.Column(db.Float)
    nota_sem1 = db.Column(db.Float)
    nota_parcial2 = db.Column(db.Float)
    nota_sem2 = db.Column(db.Float)
    
    turma_disciplina = db.relationship('TurmaDisciplina', backref='notas')


class Frequencia(db.Model):
    __tablename__ = 'frequencias'
    
    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'))
    disciplina_id = db.Column(db.Integer, db.ForeignKey('disciplinas.id'))
    ano = db.Column(db.Integer)
    semestre = db.Column(db.Integer)
    total_aulas = db.Column(db.Integer, default=0)
    faltas = db.Column(db.Integer, default=0)
    
    disciplina = db.relationship('Disciplina', backref='frequencias')


class Ocorrencia(db.Model):
    __tablename__ = 'ocorrencias'
    
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'))
    tipo_id = db.Column(db.Integer, db.ForeignKey('tipos_ocorrencia.id'))
    setor_origem_id = db.Column(db.Integer, db.ForeignKey('setores.id'))
    setor_destino_id = db.Column(db.Integer, db.ForeignKey('setores.id'))
    usuario_criador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    usuario_atendente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    prioridade = db.Column(db.String(20), default='media')
    status = db.Column(db.String(20), default='aberta')
    data_abertura = db.Column(db.DateTime, default=datetime.utcnow)
    data_prazo = db.Column(db.DateTime)
    data_conclusao = db.Column(db.DateTime)
    
    tipo = db.relationship('TipoOcorrencia')
    setor_origem = db.relationship('Setor', foreign_keys=[setor_origem_id])
    setor_destino = db.relationship('Setor', foreign_keys=[setor_destino_id])
    criador = db.relationship('Usuario', foreign_keys=[usuario_criador_id])
    atendente = db.relationship('Usuario', foreign_keys=[usuario_atendente_id])
    historico = db.relationship('HistoricoOcorrencia', backref='ocorrencia', cascade='all, delete-orphan')
    anexos = db.relationship('Anexo', backref='ocorrencia', cascade='all, delete-orphan')
    
    def esta_atrasada(self):
        if self.status == 'resolvida':
            return False
        if self.data_prazo and datetime.utcnow() > self.data_prazo:
            return True
        return False


class HistoricoOcorrencia(db.Model):
    __tablename__ = 'historico_ocorrencias'
    
    id = db.Column(db.Integer, primary_key=True)
    ocorrencia_id = db.Column(db.Integer, db.ForeignKey('ocorrencias.id'))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    acao = db.Column(db.String(50))
    descricao = db.Column(db.Text)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    
    usuario = db.relationship('Usuario')


class Anexo(db.Model):
    __tablename__ = 'anexos'
    
    id = db.Column(db.Integer, primary_key=True)
    ocorrencia_id = db.Column(db.Integer, db.ForeignKey('ocorrencias.id'))
    nome_arquivo = db.Column(db.String(200))
    caminho_arquivo = db.Column(db.String(500))
    tipo_arquivo = db.Column(db.String(100))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    data_upload = db.Column(db.DateTime, default=datetime.utcnow)
    
    usuario = db.relationship('Usuario')


class ConselhoVersao(db.Model):
    __tablename__ = 'conselho_versoes'
    
    id = db.Column(db.Integer, primary_key=True)
    conselho_id = db.Column(db.Integer, db.ForeignKey('conselhos.id'))
    versao = db.Column(db.Integer, nullable=False)
    motivo_reabertura = db.Column(db.Text)
    data_reabertura = db.Column(db.DateTime, default=datetime.utcnow)
    reaberto_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    
    consideracoes_iniciais = db.Column(db.Text)
    observacoes_gerais = db.Column(db.Text)
    ata = db.Column(db.Text)
    data_fim = db.Column(db.DateTime)
    
    reabridor = db.relationship('Usuario', backref='conselhos_reabertos')
    alunos = db.relationship('ConselhoAlunoVersao', back_populates='versao', cascade='all, delete-orphan')


class ConselhoAlunoVersao(db.Model):
    __tablename__ = 'conselho_alunos_versoes'
    
    id = db.Column(db.Integer, primary_key=True)
    versao_id = db.Column(db.Integer, db.ForeignKey('conselho_versoes.id'))
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'))
    status = db.Column(db.String(20))
    parecer = db.Column(db.Text)
    encaminhamentos = db.Column(db.Text)
    
    versao = db.relationship('ConselhoVersao', back_populates='alunos')
    aluno = db.relationship('Aluno')


class Conselho(db.Model):
    __tablename__ = 'conselhos'
    
    id = db.Column(db.Integer, primary_key=True)
    turma_id = db.Column(db.Integer, db.ForeignKey('turmas.id'))
    ano = db.Column(db.Integer)
    semestre = db.Column(db.Integer)
    tipo = db.Column(db.String(20))
    status = db.Column(db.String(20), default='aberto')
    versao_atual = db.Column(db.Integer, default=1)
    versao_original_id = db.Column(db.Integer, db.ForeignKey('conselho_versoes.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    data_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    data_fim = db.Column(db.DateTime)
    
    consideracoes_iniciais = db.Column(db.Text)
    observacoes_gerais = db.Column(db.Text)
    ata = db.Column(db.Text)
    
    # Relacionamentos
    turma = db.relationship('Turma', back_populates='conselhos')
    criador = db.relationship('Usuario', backref='conselhos_criados')
    alunos = db.relationship('ConselhoAluno', back_populates='conselho', cascade='all, delete-orphan')
    
    # Relacionamento com versões - especificando a chave estrangeira
    historico_versoes = db.relationship(
        'ConselhoVersao', 
        foreign_keys='ConselhoVersao.conselho_id',
        back_populates='conselho', 
        lazy='dynamic'
    )
    
    # Relacionamento com a versão original
    versao_original = db.relationship(
        'ConselhoVersao', 
        foreign_keys=[versao_original_id],
        back_populates='conselhos_originais'
    )

    def criar_nova_versao(self, motivo, usuario_id):
        """Cria uma nova versão do conselho baseada na atual"""
        
        # Salva versão atual no histórico
        versao_antiga = ConselhoVersao(
            conselho_id=self.id,
            versao=self.versao_atual,
            motivo_reabertura=motivo,
            reaberto_por=usuario_id,
            consideracoes_iniciais=self.consideracoes_iniciais,
            observacoes_gerais=self.observacoes_gerais,
            ata=self.ata,
            data_fim=self.data_fim
        )
        db.session.add(versao_antiga)
        db.session.flush()
        
        # Salva as decisões dos alunos nesta versão
        for aluno_conselho in self.alunos:
            aluno_versao = ConselhoAlunoVersao(
                versao_id=versao_antiga.id,
                aluno_id=aluno_conselho.aluno_id,
                status=aluno_conselho.status,
                parecer=aluno_conselho.parecer,
                encaminhamentos=aluno_conselho.encaminhamentos
            )
            db.session.add(aluno_versao)
        
        # Guarda referência à versão original se for a primeira
        if self.versao_atual == 1:
            self.versao_original_id = versao_antiga.id
        
        # Incrementa versão
        self.versao_atual += 1
        self.status = 'aberto'
        
        return versao_antiga
    
    def arquivar_versao_atual(self, motivo, usuario_id):
        """Arquiva a versão atual do conselho
        
        Args:
            motivo: Motivo da reabertura
            usuario_id: ID do usuário que está reabrindo
        """
        # Salva versão atual no histórico
        versao_antiga = ConselhoVersao(
            conselho_id=self.id,
            versao=self.versao_atual,
            motivo_reabertura=motivo,
            reaberto_por=usuario_id,
            consideracoes_iniciais=self.consideracoes_iniciais,
            observacoes_gerais=self.observacoes_gerais,
            ata=self.ata,
            data_fim=self.data_fim
        )
        db.session.add(versao_antiga)
        db.session.flush()
        
        # Salva as decisões dos alunos nesta versão
        for aluno_conselho in self.alunos:
            aluno_versao = ConselhoAlunoVersao(
                versao_id=versao_antiga.id,
                aluno_id=aluno_conselho.aluno_id,
                status=aluno_conselho.status,
                parecer=aluno_conselho.parecer,
                encaminhamentos=aluno_conselho.encaminhamentos
            )
            db.session.add(aluno_versao)
        
        # Guarda referência à versão original se for a primeira
        if self.versao_atual == 1:
            self.versao_original_id = versao_antiga.id
        
        # Incrementa versão
        self.versao_atual += 1
        self.status = 'aberto'
        
        # Mantém todos os dados para edição - não reseta nada
        
        return versao_antiga


# Adicionar back_populates após definir Conselho
ConselhoVersao.conselho = db.relationship(
    'Conselho', 
    foreign_keys=[ConselhoVersao.conselho_id],
    back_populates='historico_versoes'
)
ConselhoVersao.conselhos_originais = db.relationship(
    'Conselho', 
    foreign_keys='Conselho.versao_original_id',
    back_populates='versao_original'
)


class ConselhoAluno(db.Model):
    __tablename__ = 'conselhos_alunos'
    
    id = db.Column(db.Integer, primary_key=True)
    conselho_id = db.Column(db.Integer, db.ForeignKey('conselhos.id'))
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'))
    status = db.Column(db.String(20), default='pendente')
    parecer = db.Column(db.Text)
    encaminhamentos = db.Column(db.Text)
    ocorrencias_selecionadas = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    conselho = db.relationship('Conselho', back_populates='alunos')
    aluno = db.relationship('Aluno', backref='participacoes_conselho')

class ModeloEncaminhamento(db.Model):
    __tablename__ = 'modelos_encaminhamentos'
    
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.String(50), default='geral')
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ModeloEncaminhamento {self.titulo}>'