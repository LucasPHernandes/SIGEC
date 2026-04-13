# importar_fotos_por_nome.py (versão corrigida)
import json
import base64
import os
import re
from app import app, db
from models import Aluno
from werkzeug.utils import secure_filename

def limpar_base64(foto_base64):
    """
    Limpa e valida a string Base64
    """
    if not foto_base64:
        return None
    
    # Remove o prefixo se existir
    if ',' in foto_base64:
        foto_base64 = foto_base64.split(',')[1]
    
    # Remove espaços em branco e quebras de linha
    foto_base64 = re.sub(r'\s', '', foto_base64)
    
    # Remove caracteres não Base64
    foto_base64 = re.sub(r'[^A-Za-z0-9+/=]', '', foto_base64)
    
    # Adiciona padding se necessário (Base64 precisa ter comprimento múltiplo de 4)
    missing_padding = len(foto_base64) % 4
    if missing_padding:
        foto_base64 += '=' * (4 - missing_padding)
    
    return foto_base64


def extrair_nome_do_texto(linha):
    """
    Extrai o nome do aluno a partir de uma linha no formato:
    "📌 Nome: ADRIANO CAUDURO"
    """
    match = re.search(r'📌\s*Nome:\s*(.+)', linha)
    if match:
        return match.group(1).strip()
    return None


def extrair_imagem_da_linha(linha):
    """
    Extrai a string base64 da imagem a partir de uma linha no formato:
    "🖼️ Imagem: data:image/png;base64,iVBORw0KGgo..."
    """
    match = re.search(r'🖼️\s*Imagem:\s*(.+)', linha)
    if match:
        return match.group(1).strip()
    return None


def processar_arquivo_fotos(arquivo_path):
    """
    Processa um arquivo com blocos de dados no formato:
    
    📌 Nome: NOME DO ALUNO
    📊 Status: sucesso
    🖼️ Imagem: data:image/png;base64,...
    
    (pode ter linhas em branco entre os blocos)
    """
    with open(arquivo_path, 'r', encoding='utf-8') as f:
        conteudo = f.read()
    
    # Divide o conteúdo em blocos (separados por linhas em branco)
    blocos = re.split(r'\n\s*\n', conteudo)
    
    alunos_data = []
    
    for bloco in blocos:
        linhas = bloco.strip().split('\n')
        nome = None
        imagem = None
        
        for linha in linhas:
            if '📌 Nome:' in linha:
                nome = extrair_nome_do_texto(linha)
            elif '🖼️ Imagem:' in linha:
                imagem = extrair_imagem_da_linha(linha)
        
        if nome and imagem:
            alunos_data.append({
                'nome': nome,
                'foto_base64': imagem
            })
    
    return alunos_data


def processar_json_fotos(arquivo_json):
    """
    Processa um arquivo JSON com os dados das fotos
    Formato esperado:
    [
        {"nome": "ADRIANO CAUDURO", "foto_base64": "data:image/png;base64,..."},
        ...
    ]
    """
    with open(arquivo_json, 'r', encoding='utf-8') as f:
        dados = json.load(f)
    
    return dados


def importar_fotos_por_nome(dados_alunos):
    """
    Importa as fotos para os alunos correspondentes
    """
    
    pasta_fotos = os.path.join(app.config['UPLOAD_FOLDER'], 'fotos')
    os.makedirs(pasta_fotos, exist_ok=True)
    
    estatisticas = {
        'total': len(dados_alunos),
        'atualizados': 0,
        'nao_encontrados': 0,
        'erros': 0,
        'detalhes': []
    }
    
    with app.app_context():
        for idx, item in enumerate(dados_alunos):
            nome = item.get('nome', '').strip().upper()
            foto_base64 = item.get('foto_base64', '')
            
            if not nome:
                estatisticas['erros'] += 1
                estatisticas['detalhes'].append({'nome': nome, 'erro': 'Nome vazio'})
                continue
            
            if not foto_base64:
                estatisticas['erros'] += 1
                estatisticas['detalhes'].append({'nome': nome, 'erro': 'Foto vazia'})
                continue
            
            # Busca o aluno pelo nome
            aluno = Aluno.query.filter(db.func.upper(Aluno.nome) == nome).first()
            
            if not aluno:
                # Tenta busca aproximada (remove acentos e espaços)
                nome_sem_acento = nome.replace(' ', '').replace('Ç', 'C').replace('Ã', 'A').replace('Õ', 'O')
                alunos = Aluno.query.all()
                
                encontrado = None
                for a in alunos:
                    nome_aluno = a.nome.upper().replace(' ', '').replace('Ç', 'C').replace('Ã', 'A').replace('Õ', 'O')
                    if nome_aluno == nome_sem_acento:
                        encontrado = a
                        break
                
                if not encontrado:
                    # Tenta busca por parte do nome
                    partes = nome.split()
                    if len(partes) >= 2:
                        primeiro_nome = partes[0]
                        ultimo_nome = partes[-1]
                        alunos = Aluno.query.filter(
                            db.func.upper(Aluno.nome).like(f'%{primeiro_nome}%'),
                            db.func.upper(Aluno.nome).like(f'%{ultimo_nome}%')
                        ).all()
                        
                        if len(alunos) == 1:
                            encontrado = alunos[0]
                
                aluno = encontrado
            
            if not aluno:
                estatisticas['nao_encontrados'] += 1
                estatisticas['detalhes'].append({'nome': nome, 'erro': 'Aluno não encontrado'})
                continue
            
            try:
                # Limpa e valida a string Base64
                foto_base64_limpa = limpar_base64(foto_base64)
                
                if not foto_base64_limpa:
                    raise ValueError("Base64 inválido após limpeza")
                
                # Tenta decodificar
                try:
                    imagem_bytes = base64.b64decode(foto_base64_limpa)
                except Exception as e:
                    # Se falhar, tenta sem o padding
                    foto_base64_sem_padding = foto_base64_limpa.rstrip('=')
                    imagem_bytes = base64.b64decode(foto_base64_sem_padding)
                
                # Define o nome do arquivo
                nome_arquivo = secure_filename(f"{aluno.matricula}_{aluno.nome.replace(' ', '_')}.png")
                caminho_arquivo = os.path.join(pasta_fotos, nome_arquivo)
                
                # Salva a imagem
                with open(caminho_arquivo, 'wb') as f:
                    f.write(imagem_bytes)
                
                # Atualiza o caminho da foto no banco
                aluno.foto = f"uploads/fotos/{nome_arquivo}"
                estatisticas['atualizados'] += 1
                estatisticas['detalhes'].append({
                    'nome': aluno.nome,
                    'matricula': aluno.matricula,
                    'status': 'OK',
                    'arquivo': nome_arquivo
                })
                
                # Commit a cada 10 alunos
                if estatisticas['atualizados'] % 10 == 0:
                    db.session.commit()
                    
            except base64.binascii.Error as e:
                estatisticas['erros'] += 1
                estatisticas['detalhes'].append({
                    'nome': nome,
                    'erro': f'Erro Base64: {str(e)}'
                })
            except Exception as e:
                estatisticas['erros'] += 1
                estatisticas['detalhes'].append({
                    'nome': nome,
                    'erro': str(e)
                })
        
        db.session.commit()
    
    return estatisticas


def gerar_relatorio_importacao(estatisticas):
    """Gera um relatório da importação"""
    print("\n" + "="*70)
    print("RELATÓRIO DE IMPORTAÇÃO DE FOTOS")
    print("="*70)
    print(f"Total de registros no arquivo: {estatisticas['total']}")
    print(f"✅ Fotos atualizadas com sucesso: {estatisticas['atualizados']}")
    print(f"❌ Alunos não encontrados: {estatisticas['nao_encontrados']}")
    print(f"⚠️ Erros: {estatisticas['erros']}")
    print("-"*70)
    
    if estatisticas['detalhes']:
        print("\nDETALHES:")
        print("-"*70)
        for item in estatisticas['detalhes']:
            if 'status' in item:
                print(f"  ✅ {item['nome']} (Mat: {item['matricula']}) -> {item['arquivo']}")
            else:
                print(f"  ❌ {item['nome']} - {item['erro']}")
    
    print("="*70)


def listar_alunos_sem_foto():
    """Lista alunos que ainda não possuem foto"""
    with app.app_context():
        alunos_sem_foto = Aluno.query.filter(
            (Aluno.foto == None) | (Aluno.foto == '')
        ).order_by(Aluno.nome).all()
        
        print("\n" + "="*70)
        print(f"ALUNOS SEM FOTO ({len(alunos_sem_foto)} alunos)")
        print("="*70)
        for aluno in alunos_sem_foto:
            print(f"  {aluno.matricula} - {aluno.nome}")
        
        # Gera arquivo com nomes para facilitar
        with open('alunos_sem_foto.txt', 'w', encoding='utf-8') as f:
            for aluno in alunos_sem_foto:
                f.write(f"📌 Nome: {aluno.nome}\n📊 Status: pendente\n🖼️ Imagem: \n\n")
        
        print(f"\n✅ Arquivo 'alunos_sem_foto.txt' criado - preencha as fotos!")
        
        return alunos_sem_foto


# Função para testar uma string base64 individualmente
def testar_base64(foto_base64):
    """Testa se uma string base64 é válida"""
    try:
        foto_limpa = limpar_base64(foto_base64)
        imagem_bytes = base64.b64decode(foto_limpa)
        print(f"✅ Base64 válido! Tamanho: {len(imagem_bytes)} bytes")
        return True
    except Exception as e:
        print(f"❌ Base64 inválido: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    print("\n📸 IMPORTAÇÃO DE FOTOS DE ALUNOS - SIGEC")
    print("="*50)
    
    if len(sys.argv) < 2:
        print("\nOpções disponíveis:")
        print("  python importar_fotos_por_nome.py <arquivo>  - Importa fotos de um arquivo")
        print("  python importar_fotos_por_nome.py listar     - Lista alunos sem foto")
        print("  python importar_fotos_por_nome.py testar <base64> - Testa uma string base64")
        print("")
        print("Formatos suportados:")
        print("  - Arquivo TXT com blocos: 📌 Nome: ... / 🖼️ Imagem: ...")
        print("  - Arquivo JSON: [{\"nome\": \"...\", \"foto_base64\": \"...\"}]")
        sys.exit(0)
    
    opcao = sys.argv[1]
    
    if opcao == 'listar':
        listar_alunos_sem_foto()
    elif opcao == 'testar' and len(sys.argv) > 2:
        testar_base64(sys.argv[2])
    else:
        arquivo = opcao
        
        if not os.path.exists(arquivo):
            print(f"❌ Arquivo não encontrado: {arquivo}")
            sys.exit(1)
        
        # Detecta o tipo do arquivo
        if arquivo.endswith('.json'):
            print("📄 Processando arquivo JSON...")
            dados = processar_json_fotos(arquivo)
        else:
            print("📄 Processando arquivo TXT...")
            dados = processar_arquivo_fotos(arquivo)
        
        print(f"📊 Encontrados {len(dados)} registros de alunos")
        
        if dados:
            estatisticas = importar_fotos_por_nome(dados)
            gerar_relatorio_importacao(estatisticas)
        else:
            print("❌ Nenhum dado válido encontrado no arquivo")