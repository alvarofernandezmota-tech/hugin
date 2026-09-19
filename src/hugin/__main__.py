"""`python -m hugin` arranca el bot por consola.

Aquí no hay nada más que el enganche: el bucle está en `hugin.bot.main`,
donde se puede probar sin un terminal.
"""

import sys

from hugin.bot.main import main

if __name__ == "__main__":
    sys.exit(main())
