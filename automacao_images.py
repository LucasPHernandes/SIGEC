import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

def setup_driver():
    """Configura o driver do Chrome"""
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Descomente para executar sem interface gráfica
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def wait_and_click(driver, xpath, timeout=10):
    """Aguarda elemento e clica"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        element.click()
        time.sleep(1)  # Pequena pausa após clique
        return True
    except TimeoutException:
        print(f"Erro: Elemento não encontrado - {xpath}")
        return False

def wait_and_send_keys(driver, xpath, text, timeout=10, clear_first=True):
    """Aguarda elemento e envia texto"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        if clear_first:
            element.clear()
        element.send_keys(text)
        time.sleep(0.5)
        return True
    except TimeoutException:
        print(f"Erro: Campo de texto não encontrado - {xpath}")
        return False

def get_image_source(driver, xpath, timeout=10):
    """Obtém o source da imagem"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        img_src = element.get_attribute('src')
        return img_src
    except TimeoutException:
        print(f"Erro: Imagem não encontrada - {xpath}")
        return None

def realizar_login(driver):
    """Realiza o login no sistema"""
    print("\n🔐 Realizando login...")
    
    try:
        # 1. Clicar no primeiro campo e digitar CPF
        if not wait_and_click(driver, "//*[@id=\"username\"]"):
            print("❌ Falha ao clicar no campo do CPF")
            return False
        
        if not wait_and_send_keys(driver, "//*[@id=\"username\"]", ""):
            print("❌ Falha ao digitar CPF")
            return False
        
        print("✓ CPF digitado")
        
        # 2. Clicar no segundo campo e digitar senha
        if not wait_and_click(driver, "//*[@id=\"password\"]"):
            print("❌ Falha ao clicar no campo da senha")
            return False
        
        if not wait_and_send_keys(driver, "//*[@id=\"password\"]", ""):
            print("❌ Falha ao digitar senha")
            return False
        
        print("✓ Senha digitada")

        if not wait_and_click(driver, "//*[@id=\"kc-login\"]"):
            print("❌ Falha ao clicar no campo da senha")
            return False
        
        # Aguardar um momento para o processamento do login
        time.sleep(2)
        
        print("✅ Login realizado com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro durante o login: {str(e)}")
        return False

def process_names(names_file, output_file):
    """Processa cada nome do arquivo"""
    driver = setup_driver()
    results = []
    
    try:
        # Abrir o site inicial (você precisa adicionar a URL)
        url = "https://ru.fw.iffarroupilha.edu.br/sifw/app/usuarios.xhtml"  # SUBSTITUA PELA URL REAL
        print(f"\n🌐 Acessando: {url}")
        driver.get(url)
        time.sleep(3)
        
        # REALIZAR LOGIN PRIMEIRO
        if not realizar_login(driver):
            print("❌ Falha no login. Encerrando programa.")
            return results
        
        # Continuar com o processo principal
        print("\n📋 Iniciando processo de busca...")
        
        # Ler nomes do arquivo
        with open(names_file, 'r', encoding='utf-8') as f:
            names = [line.strip() for line in f if line.strip()]
        
        for i, name in enumerate(names, 1):
            print(f"\n{'='*50}")
            print(f"Processando {i}/{len(names)}: {name}")
            print(f"{'='*50}")
            
            try:
                # 1. Primeiro clique
                print("  → Clicando no primeiro elemento...")
                if not wait_and_click(driver, "//*[@id=\"j_idt30:j_idt31_j_idt47\"]/ul/li[1]/a"):
                    results.append({
                        'nome': name,
                        'imagem_src': None,
                        'status': 'erro_primeiro_clique'
                    })
                    continue
                
                # 2. Segundo clique
                print("  → Clicando no segundo elemento...")
                if not wait_and_click(driver, "//*[@id=\"frmMain:j_idt62\"]/tbody/tr/td[2]/div"):
                    results.append({
                        'nome': name,
                        'imagem_src': None,
                        'status': 'erro_segundo_clique'
                    })
                    continue
                
                # 3. Terceiro clique no input
                print("  → Clicando no campo de busca...")
                if not wait_and_click(driver, "//*[@id=\"frmMain:j_idt69\"]"):
                    results.append({
                        'nome': name,
                        'imagem_src': None,
                        'status': 'erro_campo_busca'
                    })
                    continue
                
                # 4. Colar o nome
                print(f"  → Digitando nome: {name}")
                if not wait_and_send_keys(driver, "//*[@id=\"frmMain:j_idt69\"]", name):
                    results.append({
                        'nome': name,
                        'imagem_src': None,
                        'status': 'erro_digitar_nome'
                    })
                    continue
                
                # 5. Clique no botão de busca
                print("  → Clicando no botão buscar...")
                if not wait_and_click(driver, "//*[@id=\"frmMain:j_idt71\"]"):
                    results.append({
                        'nome': name,
                        'imagem_src': None,
                        'status': 'erro_botao_buscar'
                    })
                    continue
                
                # Aguardar resultados carregarem
                time.sleep(2)
                
                # 6. Clique no botão da tabela
                print("  → Clicando no botão da tabela...")
                if not wait_and_click(driver, "//*[@id=\"frmMain:j_idt74:0:j_idt80\"]"):
                    results.append({
                        'nome': name,
                        'imagem_src': None,
                        'status': 'erro_botao_tabela'
                    })
                    continue
                
                # 7. Clique no li[2]
                print("  → Clicando na segunda opção...")
                if not wait_and_click(driver, "//*[@id=\"frmMain:tabView\"]/ul/li[2]"):
                    results.append({
                        'nome': name,
                        'imagem_src': None,
                        'status': 'erro_opcao_li2'
                    })
                    continue
                
                # 8. Copiar source da imagem
                print("  → Capturando imagem...")
                img_src = get_image_source(driver, "//*[@id=\"frmMain:tabView:j_idt94\"]")
                
                if img_src:
                    print(f"  ✅ SUCESSO! Imagem capturada: {img_src[:80]}...")
                    results.append({
                        'nome': name,
                        'imagem_src': img_src,
                        'status': 'sucesso'
                    })
                else:
                    print(f"  ⚠️ Imagem não encontrada para {name}")
                    results.append({
                        'nome': name,
                        'imagem_src': None,
                        'status': 'imagem_nao_encontrada'
                    })
                
                # Salvar resultados parciais
                save_results(results, output_file)
                
            except Exception as e:
                print(f"  ❌ Erro inesperado: {str(e)}")
                results.append({
                    'nome': name,
                    'imagem_src': None,
                    'status': f'erro_inesperado: {str(e)}'
                })
            
            # Pequena pausa entre processamentos
            time.sleep(2)
            
    finally:
        driver.quit()
        save_results(results, output_file)
    
    return results

def save_results(results, output_file):
    """Salva resultados em arquivo"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("RELATÓRIO DE SCRAPING\n")
        f.write(f"Total processado: {len(results)}\n")
        f.write("="*80 + "\n\n")
        
        for result in results:
            f.write(f"📌 Nome: {result['nome']}\n")
            f.write(f"📊 Status: {result['status']}\n")
            if result['imagem_src']:
                f.write(f"🖼️ Imagem: {result['imagem_src']}\n")
            f.write("-"*80 + "\n\n")

def save_results_json(results, output_file):
    """Salva resultados em JSON (formato estruturado)"""
    import json
    json_file = output_file.replace('.txt', '.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"📄 Resultados também salvos em JSON: {json_file}")

def main():
    # Configurações
    names_file = "nomes_simples.txt"  # Arquivo com os nomes
    output_file = "resultados.txt"  # Arquivo de saída
    
    # Verificar se arquivo de nomes existe
    if not os.path.exists(names_file):
        print(f"❌ Erro: Arquivo {names_file} não encontrado!")
        print(f"💡 Crie um arquivo {names_file} com um nome por linha")
        return
    
    print("\n" + "="*60)
    print("🚀 INICIANDO SISTEMA DE SCRAPING AUTOMATIZADO")
    print("="*60)
    print(f"📁 Arquivo de nomes: {names_file}")
    print(f"💾 Arquivo de saída: {output_file}")
    print("="*60)
    
    # Processar nomes
    results = process_names(names_file, output_file)
    
    # Salvar também em JSON
    save_results_json(results, output_file)
    
    # Estatísticas finais
    total = len(results)
    sucessos = sum(1 for r in results if r['status'] == 'sucesso')
    erros = total - sucessos
    
    print("\n" + "="*60)
    print("✅ PROCESSO CONCLUÍDO!")
    print("="*60)
    print(f"📊 Total processado: {total}")
    print(f"✅ Sucessos: {sucessos}")
    print(f"❌ Erros: {erros}")
    print(f"📁 Resultados salvos em: {output_file}")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()