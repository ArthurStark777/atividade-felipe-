# Segurança

Este projeto é didático, mas segue práticas de segurança reais. Esta página explica o que já
está protegido na versão em **microsserviços**, o que mudou em relação ao monólito e o que fica
como responsabilidade de quem for colocar o sistema em produção.

## O que está protegido

| Risco | Proteção |
|---|---|
| Acesso sem login | **Todo serviço** (Usuários, Inventário, Chamados e Notificações) confere o token JWT (`Authorization: Bearer ...`) antes de responder. Só `/auth/login` e `/saude` são abertos. O gateway não decide isso por eles: um serviço continua protegido mesmo que alguém o alcance sem passar pelo gateway. |
| Token falsificado | Token assinado (HS256) pelo serviço de Usuários, com validade, emissor, perfil e algoritmo fixos. Cada serviço recusa assinatura de outro segredo, token vencido, emissor diferente, perfil desconhecido e `alg: none`. |
| Segredo no código | O `JWT_SEGREDO` vem do `.env` (fora do Git) ou, se não houver `.env`, é gerado ao acaso na primeira subida e guardado em um volume do Docker. Nenhum segredo está no código. Sem segredo válido (32+ caracteres), o serviço **se recusa a iniciar** (no monólito ele inventava um por processo, o que quebraria a conferência entre serviços). |
| Só o gateway exposto | Apenas o gateway publica porta (`127.0.0.1:8000`). Serviços, bancos e Redis ficam em uma rede Docker `internal` (sem acesso de fora e sem saída para a internet). O gateway só encaminha rotas da lista permitida e recusa caminhos como `/chamados/../usuarios`. |
| Ver ou mexer no que não é seu | Permissões por perfil mantidas: o solicitante só vê os próprios chamados, notificações e painel; só técnicos e administradores atribuem e resolvem; só administradores criam usuários; só técnicos e administradores cadastram equipamentos. |
| Agir em nome de outra pessoa | O solicitante e o autor do comentário vêm do token, não do corpo da requisição. Campos extras são recusados. Não existe rota para criar notificações pela API: elas nascem só de eventos. |
| Repasse entre serviços | Ao chamar Usuários ou Inventário, o Chamados **repassa o token do próprio usuário**: o outro serviço confere de novo, e nenhum serviço ganha poderes que o usuário não tem. |
| Adivinhar senhas | Senhas guardadas só como hash **scrypt** com sal. Bloqueio temporário após 5 tentativas erradas (por e-mail e IP). O gateway define o IP real em `X-Forwarded-For`, ignorando o que o cliente mandar, para o bloqueio não ser burlado nem usado contra outra pessoa. |
| Descobrir o que existe | Chamado de outra pessoa responde 404, sem revelar que existe. A lista de usuários não mostra e-mails. Mensagem igual para e-mail inexistente e senha errada. |
| Falha de um serviço | Timeout em toda chamada entre serviços. Se Usuários ou Inventário caírem, o Chamados responde **503** com mensagem clara, antes de gravar qualquer coisa (nada fica pela metade). O gateway responde 503/504 se um serviço estiver parado ou lento. |
| XSS na tela | Todo texto vindo da API é escapado antes de entrar no HTML; não há scripts embutidos; a política CSP só permite scripts do próprio servidor. |
| Clickjacking e outros | Cabeçalhos `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` em todas as respostas do gateway. Respostas com token não ficam em cache. |
| Vazar detalhes internos | O gateway só devolve ao cliente os cabeçalhos da lista permitida (sem `Server`, `Set-Cookie` etc.). Erros de banco respondem com mensagem genérica. |
| Dados enormes | Limites de tamanho nos campos e corpo de requisição limitado a 64 KB, no gateway (mesmo sem `Content-Length`) e em cada serviço. |
| SQL injection | Acesso ao banco só pelo SQLAlchemy, com parâmetros. Cada serviço acessa **somente o seu** banco. |
| Dependências vulneráveis | Versões fixas, `pip-audit` no GitHub Actions para cada serviço e Dependabot semanal. |
| Contêineres | Todos rodam sem root (exceto o gerador de segredo, que só escreve um arquivo e termina), sistema de arquivos somente leitura, sem capacidades extras (`cap_drop: ALL`) e `no-new-privileges`. |

## O que a separação em serviços mudou (e os cuidados que ela exige)

- **O segredo agora é compartilhado.** Quem conhece o `JWT_SEGREDO` consegue criar tokens válidos
  para qualquer serviço. Por isso ele fica fora do código e só os serviços que conferem tokens o
  recebem (o gateway **não** recebe). Em produção, o ideal é assinar com chave **assimétrica**
  (RS256/EdDSA): só o serviço de Usuários teria a chave privada, e os outros, apenas a pública.
- **Perfil e situação vêm do token.** Inventário, Chamados e Notificações não têm banco de
  usuários e confiam no perfil assinado dentro do token. Se uma conta for desativada ou mudar de
  perfil, o token antigo continua valendo nesses serviços **até vencer** (`TOKEN_MINUTOS`, padrão
  60). O serviço de Usuários, dono dos dados, sempre confere o banco. Para corte imediato, seria
  preciso uma lista de tokens revogados ou uma consulta ao serviço de Usuários a cada chamada.
- **Redis sem senha.** A fila de eventos não publica porta e fica na rede interna, mas qualquer
  contêiner dessa rede poderia publicar eventos. Em produção, use senha/ACL e TLS.
- **Eventos podem se perder** se o Redis estiver fora do ar no instante da publicação (o chamado
  já foi salvo e segue valendo). O padrão *outbox* resolveria; veja o README.

## Antes de usar em produção

- Defina `JWT_SEGREDO` com pelo menos 32 caracteres aleatórios, guarde em um cofre de segredos e
  considere chaves assimétricas (veja acima).
- Rode com `DADOS_EXEMPLO=0` (os usuários de exemplo têm senha conhecida).
- Coloque o gateway atrás de HTTPS (por exemplo, um proxy reverso com certificado).
- Troque o SQLite por um banco gerenciado (PostgreSQL) para cada serviço, com backup.
- O limite de tentativas de login fica em memória no serviço de Usuários: com várias cópias dele,
  use um armazenamento compartilhado (Redis).
- Proteja o Redis (senha/ACL, TLS) e use réplicas e persistência adequadas.
- Centralize logs e acompanhe o cabeçalho `X-Request-ID` que o gateway coloca em cada chamada.

## Como relatar um problema

Encontrou uma falha? Não abra uma issue pública: envie os detalhes diretamente ao professor.
