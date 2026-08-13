## O que muda

<!-- Em uma ou duas frases. Se resolve uma issue, use "Resolve #123". -->

## Por quê

<!-- O problema que isso ataca. Se for uma heurística nova, diga qual caso real
     motivou e onde ela pode errar. -->

## Como verifiquei

<!-- Marque o que se aplica e cole o essencial. -->

- [ ] `pytest` passa (ou `pytest -m "not browser"`, se não tenho Chromium)
- [ ] Adicionei teste que falharia sem esta mudança
- [ ] Rodei contra um site real e **olhei o resultado**, não só o exit code:

```
designsys url ... --out /tmp/teste
designsys audit /tmp/teste
```

## Notas

<!-- Decisões que o diff não explica: limiares escolhidos, casos de borda
     conhecidos, o que deliberadamente ficou de fora. -->
