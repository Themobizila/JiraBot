# JiraBot - Gerenciador Inteligente de Horas e Worklog do Jira em Background

O **JiraBot** e uma ferramenta leve, confiavel e portatil para Windows desenvolvida em Python. O servico monitora em segundo plano os eventos de bloqueio e desbloqueio de tela (Lock/Unlock) do sistema operacional, cronometrando a jornada de trabalho liquida e registrando automaticamente os apontamentos no Jira Worklog conforme as janelas do seu turno.

---

## Guia Rapido: Como Configurar e Fazer Funcionar (3 Passos)

Configurar o JiraBot leva menos de 2 minutos e nao exige instalacao de pacotes:

### Passo 1: Executar o Inicializador
Na pasta do projeto, de **duplo clique** em:
```cmd
iniciar.bat
```

### Passo 2: Preencher o Assistente Inicial
Como e o seu primeiro acesso, o bot abrira automaticamente o assistente no terminal solicitando:
1. **Perfil de Turno**:
   - `1` para 8 horas (Entrada ~07:42, Saida ~17:30-18:10)
   - `2` para 6 horas cedo (Entrada ~07:45, Saida ~15:15-15:30)
   - `3` para 6 horas padrao (Entrada ~08:00, Saida ~15:30)
2. **Ticket Jira Padrao**: Chave da sua tarefa padrao no Jira (ex: `PROJ-1234` ou `CONSISABI-427`).
3. **URL do Jira**: Endereco base do Jira da sua empresa (ex: `https://jira.suaempresa.com.br` ou `https://seu-dominio.atlassian.net`).
4. **E-mail Corporativo e API Token**: Seu e-mail de login e o token de acesso pessoal gerado nas configuracoes de seguranca do Jira/Atlassian.

### Passo 3: Iniciar o Servico
No painel que se abrira em seguida:
- Digite **`1`** e pressione Enter para iniciar o bot em segundo plano.
- *(Recomendado)*: Digite **`A`** para habilitar a inicializacao automatica com o Windows (assim voce nunca mais precisa abrir o bot manualmente).
- *(Opcional)*: Execute `python make_shortcut.py` para criar o atalho oficial do JiraBot na sua Area de Trabalho.

**Pronto!** A partir deste momento, o JiraBot cuidara de toda a sua rotina:
- Ao desbloquear o PC pela manha, ele inicia o cronometro.
- Ao bloquear para o almoco, ele pausa.
- Ao retornar do almoco, ele retoma.
- Cinco minutos antes do encerramento, ele abre a janela de revisao na sua tela para voce confirmar ou editar a descricao da atividade.
- Ao bloquear o Windows no encerramento do dia, ele lanca o total trabalhado diretamente no Jira.

---

## Principais Recursos

- **Automacao Completa de Expediente (Zero Intervencao Manual Diaria)**:
  Controle inteligente de jornada baseado nos eventos nativos de sessao do Windows.
- **Janela de Revisao Pre-Saida com Foco Forcado e Popup Interativo**:
  Cinco minutos antes do fim do turno, uma janela visual surge centralizada na tela permitindo:
  1. Digitar ou editar a descricao detalhada da atividade do dia;
  2. Manter a descricao atual ou o titulo padrao da tarefa;
  3. Optar por enviar os apontamentos sem nenhuma descricao.
- **Transferencia e Remanejamento Inteligente de Horas**:
  - **Sessao de Hoje**: Permite transferir horas do dia entre tickets (total ou parcial, como `30m` ou `1.5h`) com fatiamento exato de intervalos, aceitando o numero da opcao ou a chave digitada.
  - **Direto no Jira**: Migra apontamentos antigos ja gravados entre chamados com seguranca atomica.
- **Edicao Retroativa de Descricoes de Lancamentos no Jira**:
  Permite consultar o historico de worklogs dos ultimos 7, 14 ou 30 dias e alterar os comentarios diretamente no Jira sem perder o ID do worklog original.
- **Fila Offline Resiliente de Contingencia**:
  Se a VPN ou conexao com a internet cair no encerramento do dia, o apontamento e retido na fila local (`queue.json`) e sincronizado automaticamente na proxima conexao.
- **Watchdog de Codigo e Hot-Reload em Background**:
  O servico detecta automaticamente alteracoes nos scripts do projeto e reinicia o processo em segundo plano de forma transparente.
- **100% Nativo (Sem Dependencias Externas `pip`)**:
  Construido exclusivamente sobre modulos nativos da biblioteca padrao do Python (`urllib`, `ctypes`, `tkinter`, `winreg`). Nao requer `pip install`.
- **Privacidade Total de Dados**:
  Nenhuma credencial ou historico de horas e gravado na pasta do codigo-fonte; todos os dados residem isolados no diretorio privado do seu usuario (`%USERPROFILE%\.jirabot`).
- **Icone na Bandeja do Sistema (System Tray) e Notificacoes Windows**:
  Icone ativo na area de notificacao com menu de contexto e avisos nativos Toast do Windows.
- **Relatorios de Produtividade**:
  Demonstrativos consolidados com totais trabalhados, divisao por tarefas e saldo em relacao a meta contratual.

---

## Painel de Controle Interativo (`iniciar.bat`)

Ao abrir o menu principal, as seguintes opcoes estao disponiveis:

| Opcao | Nome da Funcao | Descricao |
| :---: | :--- | :--- |
| **`[1]`** | Iniciar Bot em Background | Inicia o servico oculto (`pythonw.exe`) com monitoramento e icone na bandeja |
| **`[2]`** | Parar Bot em Background | Interrompe o processo ativo do servico em segundo plano |
| **`[X]`** | Reiniciar Bot (restart) | Finaliza o processo ativo e sobe imediatamente uma nova instancia atualizada |
| **`[3]`** | Ver Status Completo do Dia | Exibe o tempo acumulado hoje, meta, estado do cronometro e ticket ativo |
| **`[4]`** | Trocar Ticket Ativo (switch) | Altera a tarefa em tempo real; o tempo seguinte sera contabilizado no novo ticket |
| **`[M]`** | Transferir / Remanejar Horas | Transfere tempo trabalhado hoje entre tickets ou migra worklogs antigos no Jira |
| **`[D]`** | Definir / Editar Descricao | Define a descricao da atividade atual ou configura para envio sem descricao |
| **`[R]`** | Revisar Descricoes de Hoje | Lista todas as tarefas trabalhadas hoje e permite ajustar suas descricoes |
| **`[E]`** | Editar Worklogs Anteriores | Lista apontamentos historicos ja gravados no Jira e permite alterar suas descricoes |
| **`[5]`** | Relatorio Semanal (7 dias) | Tabela consolidada com horas trabalhadas nos ultimos 7 dias e saldo de jornada |
| **`[6]`** | Relatorio Mensal (30 dias) | Demonstrativo consolidado dos ultimos 30 dias de trabalho |
| **`[7]`** | Forcar Lancamento Agora (log-now) | Transmite imediatamente o tempo acumulado de hoje para o Jira sem esperar o fim do dia |
| **`[8]`** | Testar Conexao com o Jira | Valida autenticacao, conexao com a API e conectividade com o ticket padrao |
| **`[9]`** | Alternar / Criar Perfil de Turno | Permite trocar entre 8h, 6h ou criar um turno personalizado com tolerancias proprias |
| **`[T]`** | Ajustar Horario de Inicio de Hoje | Corrige o horario de entrada do dia caso tenha ligado o computador mais tarde |
| **`[P]`** | Testar Janela Grafica de Revisao | Dispara imediatamente a janela grafica de revisao pre-saida para teste na tela |
| **`[A]`** | Inicializacao com o Windows | Habilita ou desabilita a inicializacao automatica do bot ao fazer login no Windows |
| **`[C]`** | Reconfigurar Acesso / Setup | Permite alterar URL, e-mail, token de API e ticket padrao a qualquer momento |
| **`[0]`** | Sair do Painel | Fecha o terminal (o servico em segundo plano continua rodando normalmente) |

---

## Comandos de Linha de Comando (CLI)

Todas as funcionalidades tambem podem ser executadas via terminal ou atalhos:

```powershell
# Status atual em tempo real
python cli.py status

# Trocar de ticket ativo com descricao
python cli.py switch PROJ-5678 --comment "Desenvolvimento de rotina de importacao"

# Transferencia de horas de hoje (total ou parcial)
python cli.py transfer --today --source ATIVDIV-32 --target CONSISABI-427 --all
python cli.py transfer --today --source ATIVDIV-32 --target CONSISABI-427 --time 45m

# Migracao de worklogs antigos diretamente no Jira
python cli.py transfer --jira

# Definir descricao da atividade
python cli.py comment "Analise e correcao de consultas"
python cli.py comment --clear   # Configura para enviar sem descricao

# Testar a janela grafica de revisao pre-saida
python cli.py test-popup

# Revisar descricoes de hoje via terminal
python cli.py review

# Listar e editar historico de worklogs no Jira
python cli.py edit-worklogs --days 14

# Forcar envio imediato de horas
python cli.py log-now
python cli.py log-now --no-comment

# Ajustar horario de inicio do dia
python cli.py adjust-start 07:45

# Controle do servico
python cli.py start
python cli.py stop
python cli.py restart

# Relatorios de produtividade
python cli.py report --days 7
python cli.py report --month

# Gerenciar inicializacao automatica com o Windows
python cli.py autostart enable
python cli.py autostart disable

# Testes de conexao com o Jira
python cli.py test-jira
```

---

## Onde Ficam Salvos os Dados e Seguranca

Para garantir seguranca e permitir compartilhar a pasta do projeto sem riscos, os dados pessoais e credenciais sao persistidos exclusivamente no perfil do usuario do Windows:

**Caminho Local:**
`C:\Users\<SeuUsuario>\.jirabot\` (ou `%USERPROFILE%\.jirabot`)

- `config.json`: Credenciais do Jira, URL, token de API e definicoes de perfis de turno.
- `state.json`: Estado do dia atual em tempo real (intervalos de trabalho, tickets e status do cronometro).
- `queue.json`: Fila offline de contingencia com apontamentos pendentes de sincronizacao.
- `history.json`: Historico consolidado de fechamento de dias anteriores.
- `jirabot.log`: Registro de auditoria de eventos e comunicacao com o Jira.
- `jirabot.pid`: Identificador do processo Windows do servico em execucao em segundo plano.

---

## Como Compartilhar com um Colega de Equipe

Se desejar enviar o JiraBot para um colega utilizar na maquina dele:

1. **Compacte a pasta do projeto em um arquivo .zip**, garantindo deixar de fora:
   - As pastas `__pycache__` (arquivos temporarios compilados);
   - A pasta `relatorios/` (documentos internos da sua maquina);
   - O arquivo `JiraBot.lnk` (atalho com os caminhos da sua maquina).
2. **Na maquina do seu colega**:
   - Basta descompactar a pasta em qualquer local;
   - Dar duplo clique em `iniciar.bat`;
   - O assistente automatico solicitara os dados dele no primeiro acesso;
   - Para criar o atalho com o icone na Area de Trabalho dele, basta rodar `python make_shortcut.py`.

---

## Estrutura dos Arquivos do Codigo-Fonte

- `iniciar.bat`: Inicializador de duplo clique para Windows.
- `requirements.txt`: Documento formal de requisitos (confirma utilizacao 100% da biblioteca padrao).
- `cli.py`: Interface de linha de comando, menu interativo e despachante de comandos.
- `daemon.py`: Gerenciador do servico em segundo plano, watchdog e recarga automatica de codigo.
- `engine.py`: Motor de regras de negocio, cronometro, gestao de pausas e integracao de eventos.
- `watcher.py`: Listener nativo Win32 (mensagens `WM_WTSSESSION_CHANGE`) para deteccao de Lock/Unlock.
- `jira_client.py`: Integracao HTTP com a API REST do Jira, filas offline, envio, edicao e migracao de worklogs.
- `review_dialog.py`: Dialogo grafico pre-saida (Tkinter) e interfaces de revisao e edicao retroativa.
- `tray.py`: Integracao com a Area de Notificacao (System Tray) da Barra de Tarefas do Windows.
- `storage.py`: Modelos de dados (`DailyState`, `TimeInterval`, `QueueItem`), fatiamento de horas e persistencia atomica.
- `history.py`: Formatador de relatorios tabulares de produtividade.
- `config.py`: Definicoes de configuracao, validacoes de URL e modelos de perfis de turno.
- `make_shortcut.py`: Gerador de atalhos executaveis com icone para a Barra de Tarefas e Desktop.
- `tests.py`: Suite de testes unitarios automatizados.
