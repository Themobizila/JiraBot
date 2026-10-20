# JiraBot - Gerenciador Inteligente de Horas e Worklog do Jira em Background

O **JiraBot** e uma ferramenta leve, confiavel e portatil para Windows desenvolvida em Python. O servico monitora em segundo plano os eventos de bloqueio e desbloqueio de tela (Lock/Unlock) do sistema operacional, cronometrando a jornada de trabalho liquida e registrando automaticamente os apontamentos no Jira Worklog conforme as janelas do seu turno.

Conta com interface de terminal interativa, painel Web completo para navegador (com suporte a Dark Mode, visao semanal e lancamentos em lote), icone na area de notificacao (System Tray) e sistema de atualizacao automatica multi-usuario com total isolamento de credenciais.

---

## Como Instalar e Usar pela Primeira Vez (Autoatendimento da Equipe)

O JiraBot foi desenvolvido para ser **100% nativo** sobre a biblioteca padrao do Python, sem necessidade de instalar pacotes adicionais via `pip`.

### Opcao 1: Download Direto do Pacote ZIP (Recomendado para Usuarios Comuns)
1. Baixe o pacote oficial atualizado do repositorio:  
   **[Download do JiraBot (ZIP)](https://github.com/Themobizila/JiraBot/archive/refs/heads/main.zip)**
2. Clique com o botao direito no arquivo baixado e selecione **"Extrair Tudo"** (ex: na sua Area de Trabalho ou em `C:\dev\JiraBot`).
3. Entre na pasta descompactada e de duplo clique em:
   ```cmd
   iniciar.bat
   ```
   *(Ou em `iniciar_web.bat` se preferir configurar direto pelo navegador).*

### Opcao 2: Clonando via Git (Desenvolvedores e TI)
```cmd
git clone https://github.com/Themobizila/JiraBot.git
cd JiraBot
iniciar.bat
```

---

## Assistente de Primeiro Acesso

Como e a primeira vez que o aplicativo roda no seu computador, o JiraBot detecta automaticamente a ausencia de configuracoes locais e inicia o assistente guiado solicitando:

1. **Perfil de Turno**:
   - `1` para 8 horas (Entrada ~07:42, Saida ~17:30-18:10)
   - `2` para 6 horas cedo (Entrada ~07:45, Saida ~15:15-15:30)
   - `3` para 6 horas padrao (Entrada ~08:00, Saida ~15:30)
   - `4` para criar um turno totalmente personalizado com suas proprias tolerancias.
2. **Ticket Jira Padrao**: Chave da sua tarefa padrao no Jira (ex: `PROJ-1234` ou `ATIVDIV-32`).
3. **URL do Jira**: Endereco base do Jira corporativo (ex: `https://suaempresa.atlassian.net`).
4. **E-mail Corporativo e API Token**: Seu e-mail de login e o token de acesso pessoal gerado nas configuracoes de seguranca da sua conta Atlassian.

Ao final, o assistente valida a conexao com a API do Jira na mesma hora e salva suas credenciais exclusivamente no seu perfil do Windows.

---

## Inicializacao do Servico Diario

No menu que se abrira em seguida:
- Digite **`1`** e pressione Enter para iniciar o bot em segundo plano.
- *(Altamente Recomendado)*: Digite **`A`** para habilitar a inicializacao automatica com o Windows (assim o JiraBot inicia sozinho todo dia ao ligar o computador).
- *(Opcional)*: Execute `python make_shortcut.py` para criar o atalho oficial na sua Area de Trabalho.

**Pronto! A partir deste momento, o JiraBot cuida de toda a sua rotina:**
- Ao desbloquear o PC pela manha, ele inicia o cronometro.
- Ao bloquear para o almoco, ele pausa.
- Ao retornar do almoco, ele retoma.
- Cinco minutos antes do encerramento, ele abre a janela de revisao na sua tela para voce confirmar ou editar a descricao da atividade.
- Ao bloquear o Windows no encerramento do dia, ele lanca o total trabalhado diretamente no Jira.

---

## Painel Web Interativo (`iniciar_web.bat`)

O JiraBot inclui uma Single-Page Application visual que roda localmente em `http://127.0.0.1:8765`:

Para abrir a interface visual a qualquer momento:
- De duplo clique em `iniciar_web.bat`; OU
- No menu do terminal (`iniciar.bat`), digite **`W`**; OU
- No icone da bandeja do Windows (System Tray), clique em **"Abrir Painel Web no Navegador"**.

### Recursos do Painel Web:
1. **Painel do Dia e Horarios**: Visualizacao em tempo real do cronometro, progresso da meta, horarios de inicio, almoco, retorno e encerramento, alem de edicao de intervalos e descricoes.
2. **Visualizacao Semanal**: Navegacao por semanas do ano com cartoes consolidados de horas trabalhadas, meta semanal, saldo e detalhamento dia a dia.
3. **Gerenciador de Worklogs do Jira**: Consulta todos os lancamentos anteriores por periodo (7 a 90 dias) ou por ticket, permitindo editar horarios, descricoes e **remanejar lancamentos entre tickets** com seguranca atomica.
4. **Lancamentos em Lote (Recuperacao Retroativa)**: Grade editavel para preencher e lancar no Jira semanas inteiras de uma so vez quando o bot ficou desligado ou durante ferias/atestados.
5. **Dark Mode / Modo Claro**: Alternador de tema completo persistido no navegador.
6. **Configuracoes e Auto-Updater**: Painel de gerenciamento de turnos, mascaramento de tokens e atualizacao do aplicativo em 1 clique.

---

## Como Funcionam as Atualizacoes Automaticas

O modulo `updater.py` garante que toda a equipe mantenha o JiraBot atualizado sem risco de perda de configuracoes:

- **100% de Isolamento**: Todas as configuracoes pessoais e tokens ficam salvos em `%USERPROFILE%\.jirabot\config.json` e **nunca** sao substituidos em atualizacoes.
- **Atualizacao em 1 Clique**: No Painel Web (Aba Configuracoes), basta clicar em **"Atualizar Aplicativo Agora (1 Clique)"** para baixar a versao mais recente do GitHub.
- **Atualizacao ao Iniciar**: Se a opcao *"Buscar e aplicar atualizacoes automaticamente ao iniciar o JiraBot"* estiver marcada, o bot verifica silenciosamente o GitHub toda vez que inicia e atualiza os arquivos `.py` e `.bat` automaticamente.

---

## Menu de Opcoes do Terminal (`iniciar.bat`)

| Opcao | Nome da Funcao | Descricao |
| :---: | :--- | :--- |
| **`[W]`** | Abrir Painel Web | Inicia e abre o Painel Web Interativo no navegador padrao |
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
| **`[7]`** | Forcar Lancamento Agora | Transmite imediatamente o tempo acumulado de hoje para o Jira sem esperar o fim do dia |
| **`[8]`** | Testar Conexao com o Jira | Valida autenticacao, conexao com a API e conectividade com o ticket padrao |
| **`[9]`** | Alternar / Criar Perfil de Turno | Permite trocar entre 8h, 6h ou criar um turno personalizado com tolerancias proprias |
| **`[T]`** | Ajustar Horario de Inicio | Corrige o horario de entrada do dia caso tenha ligado o computador mais tarde |
| **`[P]`** | Testar Janela Grafica de Revisao | Dispara imediatamente a janela grafica de revisao pre-saida para teste na tela |
| **`[A]`** | Inicializacao com o Windows | Habilita ou desabilita a inicializacao automatica do bot ao fazer login no Windows |
| **`[U]`** | Verificar / Atualizar Aplicativo | Consulta o GitHub e atualiza os arquivos do sistema automaticamente |
| **`[C]`** | Reconfigurar Acesso / Setup | Permite alterar URL, e-mail, token de API e ticket padrao a qualquer momento |
| **`[0]`** | Sair do Painel | Fecha o terminal (o servico em segundo plano continua rodando normalmente) |

---

## Onde Ficam Salvos os Dados e Seguranca

Para garantir seguranca absoluta e permitir compartilhamento do codigo sem riscos de exposicao de dados, nenhum token e gravado na pasta do projeto:

**Diretorio Privado Local:**
`%USERPROFILE%\.jirabot\` (ex: `C:\Users\<SeuUsuario>\.jirabot\`)

- `config.json`: Credenciais do Jira, URL, API Token pessoal e perfis de turno do usuario.
- `state.json`: Estado do dia atual em tempo real (intervalos de trabalho, tickets e status do cronometro).
- `worklog_schedules.json`: Mapeamento de horarios de inicio, pausa de almoco, retorno e encerramento de cada apontamento.
- `queue.json`: Fila offline de contingencia com apontamentos retidos caso a rede caia.
- `history.json`: Historico consolidado de fechamento de dias anteriores.
- `jirabot.log`: Registro de auditoria de eventos e comunicacao com o Jira.
- `jirabot.pid`: Identificador do processo Windows do servico em execucao em segundo plano.

---

## Estrutura dos Arquivos do Codigo-Fonte

- `iniciar.bat`: Inicializador rapido do terminal interativo.
- `iniciar_web.bat`: Inicializador rapido do Painel Web no navegador.
- `web_panel.py`: Servidor HTTP multithread local e Single-Page Application completa (HTML5/CSS3/JS puro).
- `updater.py`: Modulo de atualizacao automatica via GitHub (ZIP ou Git) e isolamento multi-usuario.
- `cli.py`: Interface de linha de comando, menu interativo e despachante de comandos.
- `daemon.py`: Gerenciador do servico em segundo plano, watchdog e recarga automatica de codigo.
- `engine.py`: Motor de regras de negocio, cronometro, gestao de pausas e integracao de eventos.
- `watcher.py`: Listener nativo Win32 (mensagens `WM_WTSSESSION_CHANGE`) para deteccao de Lock/Unlock.
- `jira_client.py`: Integracao HTTP com a API REST do Jira, filas offline, envio, edicao e migracao de worklogs.
- `review_dialog.py`: Dialogo grafico pre-saida (Tkinter) com foco forcado para revisao de atividades.
- `tray.py`: Integracao com a Area de Notificacao (System Tray) da Barra de Tarefas do Windows.
- `storage.py`: Modelos de dados (`DailyState`, `TimeInterval`, `QueueItem`), fatiamento de horas e persistencia atomica.
- `history.py`: Formatador de relatorios tabulares de produtividade.
- `config.py`: Definicoes de configuracao, validacoes de URL e modelos de perfis de turno.
- `notifier.py`: Modulo de notificacoes nativas Toast do Windows.
- `make_shortcut.py`: Gerador de atalhos executaveis com icone para a Barra de Tarefas e Desktop.
- `requirements.txt`: Documento formal de requisitos (confirma utilizacao 100% da biblioteca padrao).
- `tests.py`: Suite de testes unitarios automatizados.
