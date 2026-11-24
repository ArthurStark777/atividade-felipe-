# Roteiro do vídeo (4 a 6 minutos)

Gravação de tela com a sua voz, sem edição. A ordem abaixo é a que o [DESAFIO](../DESAFIO.md) pede.
**Fale com as suas palavras**: os "pontos de fala" são só um lembrete do que não pode faltar.

Tempo sugerido: **≈ 5 min 40 s**. Publique no YouTube como **não listado** (ou no Google Drive com
acesso para quem tiver o link) e cole o link no topo do `README.md`.

## Antes de gravar (5 minutos)

1. Deixe o terminal com fonte grande e duas abas: uma na raiz do projeto, outra para os `curl`.
2. Rode uma vez `docker compose up --build` para as imagens ficarem em cache (a subida no vídeo será rápida).
   Depois `docker compose down -v` para começar do zero, com os dados de exemplo.
3. Deixe aberto: o README no GitHub (para o diagrama renderizado) e `http://localhost:8000` em uma janela anônima.
4. Rode `python scripts/teste_integracao.py --falha` uma vez, **antes** de gravar. Se tudo passar, o que você vai
   mostrar no vídeo vai funcionar. Depois `docker compose down -v` de novo.

## 1. A arquitetura (≈ 0:45)

Mostre o **diagrama Mermaid do README** (renderizado no GitHub).

Pontos de fala:
- Antes: uma aplicação, um banco. Agora: **três serviços** (Usuários, Inventário, Chamados) mais Notificações,
  cada um com **o seu banco**, e um **gateway** como única porta de entrada.
- O Chamados chama Usuários e Inventário por **HTTP**, com **timeout**, repassando o **token** do usuário.
- Linhas tracejadas (bônus): o Chamados publica **eventos** no Redis e a Notificações os consome.
- Só o gateway está exposto; o resto fica em uma rede interna.

## 2. Tudo subindo (≈ 0:30)

```bash
docker compose up --build
```
Espere ficar pronto (em outro terminal ou depois de `Ctrl+C` e `up -d`):
```bash
docker compose ps
```
Mostre todos **healthy** e que **só o gateway tem porta publicada** (`127.0.0.1:8000->8000`).
Opcional: `curl http://localhost:8000/saude` mostrando os quatro serviços `ok`.

## 3. O fluxo completo pela tela (≈ 1:30)

Em `http://localhost:8000`, entre como **carla@empresa.com** (senha `Helpdesk2026`).

1. Mostre o painel e o indicador de **serviços no ar** no topo.
2. **Abra um chamado** escolhendo um equipamento (ex.: o desktop do Financeiro).
3. **Atribua** a um técnico (Carla).
4. **Resolva**.
5. **Feche**.
6. Mostre as **notificações** aparecendo na lateral.

Pontos de fala: "tudo isso passa pelo gateway, no mesmo endereço do monólito"; ao abrir com equipamento,
"o Chamados perguntou ao Inventário, por HTTP, se o equipamento existe"; ao atribuir, "perguntou ao Usuários
se a pessoa é técnica".

## 4. A segurança funcionando (≈ 0:45)

Sem token:
```bash
curl -i http://localhost:8000/chamados
# HTTP/1.1 401 Unauthorized
```
Solicitante sem ver o chamado de outra pessoa (o chamado **#2** é do Bruno; a Ana não pode vê-lo):
```bash
TOKEN_ANA=$(curl -s http://localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"ana@empresa.com","senha":"Helpdesk2026"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -i http://localhost:8000/chamados/2 -H "Authorization: Bearer $TOKEN_ANA"
# HTTP/1.1 404 Not Found   (nem revela que o chamado existe)
```
Ou, pela tela: entre como **ana@empresa.com** e mostre que só aparecem os chamados dela.

Pontos de fala: "o token é conferido em **cada** serviço, não só no gateway"; "o segredo vem do `.env`/volume,
não está no código"; "o Chamados **repassa o token** ao chamar os outros".

## 5. Bancos separados (≈ 0:30)

```bash
docker volume ls --filter name=helpdesk_dados
docker compose exec usuarios ls -lh /dados
docker compose exec chamados python -c "import sqlite3; c=sqlite3.connect('/dados/chamados.db'); print([r[0] for r in c.execute(\"select name from sqlite_master where type='table'\")])"
docker compose exec usuarios python -c "import sqlite3; c=sqlite3.connect('/dados/usuarios.db'); print([r[0] for r in c.execute(\"select name from sqlite_master where type='table'\")])"
```
Mostre que o banco de Chamados tem só `chamados` e `comentarios` (**não** tem a tabela de usuários), e que cada serviço
tem o seu volume. Comente: "não existe mais chave estrangeira entre serviços: o Chamados guarda só o número do
solicitante e confere por HTTP".

## 6. A falha de um serviço (≈ 1:00)

```bash
docker compose stop inventario
```
Na tela (já logado como Carla ou Ana, com a página carregada **antes** de parar o serviço).
**Não aperte F5**: ao recarregar sem o Inventário, a lista de equipamentos da tela fica vazia, e você precisa dela
para mostrar o erro no passo 3.

1. O indicador no topo muda para `inventario: fora do ar` (leva até 5 segundos).
2. Faça uma ação que não depende do Inventário (por exemplo, atribuir ou resolver outro chamado): a **lista de
   chamados** e os nomes dos **usuários** continuam carregando. Se quiser, mostre também no terminal:
   `curl -s http://localhost:8000/usuarios -H "Authorization: Bearer $TOKEN_ANA"` (200).
3. **Abra um chamado escolhendo um equipamento**: aparece o erro claro
   *"O serviço de Inventário está indisponível no momento. Tente novamente em instantes."* (503), sem travar nada.
4. Abra um chamado **sem** equipamento: funciona.

Depois:
```bash
docker compose start inventario
```
Espere o indicador voltar a `ok` e abra um chamado com equipamento de novo.

Pontos de fala: "isso é o `timeout` + tratamento de falha"; "a conferência acontece **antes** de gravar, então
nada fica pela metade".

## 7. O que é novo em relação ao monólito (≈ 0:40)

- **Melhor**: cada serviço pode ser publicado sozinho; uma falha fica isolada (o que vimos); dá para escalar só
  o que precisa; cada parte tem dono, banco e testes.
- **Mais difícil**: agora existe a **rede no meio** (latência, falhas, timeouts); sem transação nem chave
  estrangeira entre serviços (consistência é por conferência na hora); o token e o segredo precisam estar certos em
  vários lugares; mais contêineres para operar e mais difícil depurar.
- Cite uma decisão sua (por exemplo: Redis Streams em vez de publicar/assinar, para os avisos não se perderem
  quando a Notificações cai; ou conferir o token em cada serviço em vez de só no gateway).

## 8. Bônus (≈ 0:30)

Eventos chegando à Notificações:
```bash
docker compose logs notificacoes --tail 8
docker compose exec redis redis-cli XLEN chamados.eventos
docker compose exec redis redis-cli XRANGE chamados.eventos - + COUNT 2
```
Se quiser provar "Notificações cai e os chamados continuam":
```bash
docker compose stop notificacoes      # abra um chamado na tela: funciona
docker compose start notificacoes     # os avisos chegam em seguida
```
Testes rodando (um serviço, e mostre a aba **Actions** do GitHub com todos verdes):
```bash
cd servicos/chamados && pytest -q
```

---

### Lista rápida do que o professor vai procurar no vídeo

- [ ] Diagrama explicado (serviços, bancos, gateway, HTTP e eventos)
- [ ] `docker compose up --build` e `docker compose ps` com tudo no ar
- [ ] Fluxo completo pela tela: abrir, atribuir, resolver, fechar
- [ ] 401 sem token e solicitante sem ver chamado de outra pessoa
- [ ] Cada serviço com o seu banco
- [ ] `docker compose stop inventario`: usuários e chamados funcionam; abrir com equipamento dá erro claro; `start` de novo
- [ ] O que mudou: o que ficou melhor e o que ficou mais difícil
- [ ] Bônus (se fez): eventos na Notificações e testes
