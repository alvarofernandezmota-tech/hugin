"""hugin — el cerebro de un bot que atiende a gente, sin saber por donde entra.

Tres paquetes:

- `mente`: entender lo que dicen y decidir que contestar.
- `negocio`: de que negocio se habla — sus datos, sus frases, su agenda.
- `guardado`: donde se escribe y como.

Lo que **no** esta aqui es como llega la conversacion. Una llamada de
telefono, un chat de Telegram o una ventana web son la misma conversacion
vista por sitios distintos, y el cerebro no tiene por que enterarse de cual
es: recibe texto, devuelve texto.

Por eso `hugin` no importa nada de ningun canal. Si algun dia un modulo de
aqui necesita `telefono`, el corte esta mal hecho y lo que hay que mover es
la decision, no el import.

## Como se usa

Este paquete vive en `hugin/`, dentro del repo del producto, y lo que va al
`sys.path` es la raiz del repositorio (ADR-024). Los imports salen solos:

    from hugin.mente import recepcion
    from hugin.negocio import negocio as negocios

Nombre: los dos cuervos de Odin son Hugin —el pensamiento— y Munin —la
memoria—. Este es el que piensa.
"""
