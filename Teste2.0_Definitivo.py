import pandas as pd
import time
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import fitz 
import re
import datetime
from openpyxl import load_workbook
from openpyxl.styles import PatternFill
import concurrent.futures

# --- CONFIGURAÇÕES ---
# Data Automática
DATA_ALVO = datetime.datetime.now().strftime("%d/%m/%Y")
# DATA_ALVO = "08/12/2025" 

NOME_ARQUIVO_FINAL = f"Relatorio_Geral_{DATA_ALVO.replace('/','-')}.xlsx"
JORNAL_ID = 515 


PAGINA_INICIAL = 1
PAGINA_FINAL = 400 


THREADS = 50

# --- SESSÃO DE REDE OTIMIZADA ---
session = requests.Session()
retries = Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retries, pool_connections=THREADS, pool_maxsize=THREADS)
session.mount('https://', adapter)
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

def processar_pagina_turbo(pagina):
    """
    Baixa e lê a página usando PyMuPDF (fitz) na memória.
    """
    url = f"https://pesquisa.in.gov.br/imprensa/servlet/INPDFViewer?jornal={JORNAL_ID}&pagina={pagina}&data={DATA_ALVO}&captchafield=firstAccess"
    dados_pagina = []
    
    try:
        response = session.get(url, timeout=15)
        
        if response.status_code == 200 and b"%PDF" in response.content:
            

            with fitz.open(stream=response.content, filetype="pdf") as doc:
                for page in doc:
                    texto = page.get_text("text") 
                    
                    if not texto: continue
                    
                    
                    linhas = texto.split('\n')
                    
                    
                    regex_padrao = re.compile(r'(.+?)\s*/\s*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})')
                    verbos_atividade = ["ARMAZENAR", "DISTRIBUIR", "EXPEDIR", "TRANSPORTAR", "COMÉRCIO", "FABRICAR", "IMPORTAR", "DISPENSAR"]
                    
                    empresa_obj = None
                    
                    for linha in linhas:
                        linha = linha.strip()
                        if not linha: continue
                        
                        match = regex_padrao.search(linha)
                        
                        
                        if match:
                            if empresa_obj: dados_pagina.append(empresa_obj)
                            
                            nome_sujo = match.group(1).strip()
                            nome = re.sub(r'^[\d\.\-\s]+', '', nome_sujo)
                            
                            if len(nome) > 4:
                                empresa_obj = {
                                    "Data": DATA_ALVO,
                                    "Página": pagina,
                                    "Empresa": nome,
                                    "CNPJ": match.group(2),
                                    "Atividades": [],
                                    "Status": "Em Análise",
                                    "Link": url.replace("servlet/INPDFViewer", "jsp/visualiza/index.jsp")
                                }
                            else:
                                empresa_obj = None
                        
                       
                        elif empresa_obj:
                            linha_upper = linha.upper()
                            for verbo in verbos_atividade:
                                if linha_upper.startswith(verbo):
                                    empresa_obj["Atividades"].append(linha)
                                    break
                            
                            if "DEFERIDO" in linha_upper or "CONCESSÃO" in linha_upper or "AUTORIZA" in linha_upper:
                                empresa_obj["Status"] = "LIBERADA"
                            elif "INDEFERIDO" in linha_upper:
                                empresa_obj["Status"] = "INDEFERIDO"
                    
                    if empresa_obj: dados_pagina.append(empresa_obj)
            
            return dados_pagina
        else:
            return None 

    except Exception:
        return []

def robo_turbo_max():
    print(f"===========================================================")
    print(f" ROBÔ DOU FÓRMULA 1 (PyMuPDF) - {DATA_ALVO}")
    print(f"===========================================================")
    
    inicio = time.time()
    todos_dados = []
    paginas_lidas = 0
    
 
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as executor:
        futuros = {executor.submit(processar_pagina_turbo, pag): pag for pag in range(PAGINA_INICIAL, PAGINA_FINAL + 1)}
        
        for future in concurrent.futures.as_completed(futuros):
            pag = futuros[future]
            try:
                resultado = future.result()
                paginas_lidas += 1
                
                if resultado:
                    todos_dados.extend(resultado)
                
                if paginas_lidas % 50 == 0:
                    tempo_decorrido = time.time() - inicio
                    velocidade = paginas_lidas / tempo_decorrido
                    print(f"   ...{paginas_lidas}/{PAGINA_FINAL} páginas ({velocidade:.1f} págs/seg)...")
                    
            except Exception:
                pass

    tempo_total = time.time() - inicio
    print(f"\n>>> Concluído em {tempo_total:.2f} segundos!") 

   
    if todos_dados:
        print(f">>> Salvando {len(todos_dados)} registros...")
        
        todos_dados.sort(key=lambda x: x['Página'])
        
        for item in todos_dados:
            item["Atividades"] = " | ".join(item["Atividades"])
            
        df = pd.DataFrame(todos_dados)
        
        if os.path.exists(NOME_ARQUIVO_FINAL):
            try:
                with pd.ExcelWriter(NOME_ARQUIVO_FINAL, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
                    reader = pd.read_excel(NOME_ARQUIVO_FINAL)
                    df.to_excel(writer, index=False, header=False, startrow=len(reader)+1)
            except:
                df.to_excel(NOME_ARQUIVO_FINAL, index=False)
        else:
            df.to_excel(NOME_ARQUIVO_FINAL, index=False)
            
        
        try:
            wb = load_workbook(NOME_ARQUIVO_FINAL)
            ws = wb.active
            fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
            for col in range(1, 7):
                ws.cell(row=1, column=col).fill = fill
            wb.save(NOME_ARQUIVO_FINAL)
        except: pass
        
        print(f"✅ RELATÓRIO PRONTO: {NOME_ARQUIVO_FINAL}")
    else:
        print("\n🚫 Nenhuma empresa encontrada hoje.")

if __name__ == "__main__":
    robo_turbo_max()