# FRONTERAS

La historia que dibujó el mapa. Fábrica de documentales cortos con mapas en relieve, hecha por naked · agencia creativa.

Le escribes un tema a tu bot de Telegram y en unos minutos te regresa el video terminado, con título, descripción y fuentes listos para YouTube.

## Cómo funciona por dentro

| Paso | Qué hace | Archivo |
|---|---|---|
| 1 | Claude investiga en internet, verifica con dos fuentes o más, escribe el guion y dirige cada escena | `fronteras/guionista.py` |
| 2 | ElevenLabs graba una sola toma y devuelve el segundo exacto de cada palabra | `fronteras/voz.py` |
| 3 | Se compone una música original para ese video | `fronteras/musica.py` |
| 4 | El motor anima los mapas al ritmo de la voz y renderiza en 1080x1920 (o 1920x1080) | `fronteras/motor.py` |
| 5 | Todo junto, de tema a video | `fronteras/fabrica.py` |
| 6 | El bot de Telegram que recibe temas y entrega videos | `fronteras/bot.py` |

Comparado con la plantilla comprada, aquí no hay panel ni pasos manuales. La voz no se baja ni se sube a mano, no se transcribe aparte (los tiempos vienen con la voz) y se graba una sola toma, así que gasta menos créditos y menos tiempo.

## Lo que cuesta cada video (aproximado)

| Proveedor | Para qué | Costo aproximado |
|---|---|---|
| Anthropic (Claude API) | guion investigado y escenas | entre 0.10 y 0.40 dólares por video |
| ElevenLabs | voz de unos 55 segundos | unos 900 créditos por video, depende de tu plan |
| Servidor | tener el bot prendido siempre | unos 5 dólares al mes |

## Las cuatro llaves que necesitas

1. **Anthropic API.** Entra a console.anthropic.com, crea una cuenta, carga saldo (con 10 dólares alcanza para decenas de videos) y en API Keys crea una llave. Empieza con `sk-ant-`.
2. **ElevenLabs API.** En elevenlabs.io entra a tu perfil, luego API Keys, y crea una llave. Dale permiso de Text to Speech.
3. **Bot de Telegram.** En Telegram abre @BotFather, escribe `/newbot`, ponle nombre (por ejemplo FRONTERAS Fábrica) y copia el token que te da.
4. **Tu número de usuario de Telegram.** Cuando el bot ya esté prendido, escríbele `/start` y te dice tu número. Ponlo en `TELEGRAM_USUARIOS` para que solo tú puedas pedir videos.

## Subirlo a la nube con Railway (lo más fácil)

1. Crea un repositorio privado en GitHub llamado `fronteras` y sube esta carpeta completa.
2. Entra a railway.com con tu cuenta de GitHub y elige New Project, luego Deploy from GitHub repo, luego `fronteras`.
3. Railway detecta el `Dockerfile` solo. En la pestaña Variables pega las llaves como vienen en `.env.example`.
4. Espera a que diga Deployed. Abre tu bot en Telegram y escribe `/start`.
5. Copia tu número de usuario, ponlo en la variable `TELEGRAM_USUARIOS` y deja que Railway reinicie.

Para que los videos salgan rápido, en Railway sube el servicio a 2 vCPU y 4 GB de memoria. Con eso un short tarda de 3 a 5 minutos.

## Órdenes del bot

| Escribes | Pasa |
|---|---|
| un tema cualquiera | short vertical de unos 55 segundos |
| `/horizontal tema` | versión 16:9 para YouTube normal |
| `/ideas` | diez temas nuevos con dato verificable |
| `/estado` | qué está produciendo ahora |

## Probarlo en una computadora

```
pip install -r requirements.txt
cp .env.example .env        # y pega tus llaves
python -m fronteras.fabrica "por qué Bolivia no tiene mar"
```

El video queda en `videos/`.

## Créditos y licencias

Relieve y fronteras de Natural Earth, dominio público. Tipografías Noto Serif Display e Inter, licencia SIL Open Font. Música compuesta por el propio sistema. Ningún archivo de la plantilla comprada se usa aquí.
