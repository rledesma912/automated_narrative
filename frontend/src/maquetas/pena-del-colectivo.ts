/**
 * Spec-530 S0: datos fijos de las maquetas del asistente. Salen de las pruebas del
 * 2026-09-25 con «la pena del colectivo» (scripts/research/530/): preguntas del
 * Consultor, escaleta del Planificador y los avisos que el Verificador tendría que dar.
 * Se borran cuando las vistas reales (S4) lean del Core.
 */

export type Semaforo = "cumple" | "parcial" | "falta" | "intencional";

export const PASOS = [
  { id: "direccion", label: "Dirección", href: "/maquetas/direccion" },
  { id: "taller", label: "Taller", href: "/maquetas/taller" },
  { id: "escaleta", label: "Escaleta", href: "/maquetas/escaleta" },
  { id: "relato", label: "Relato", href: "#" },
] as const;

export const SEMAFORO: Record<Semaforo, { label: string; cls: string; dot: string }> = {
  cumple: { label: "Cumple", cls: "text-forge-success bg-forge-success-bg border-forge-success-border", dot: "bg-forge-success" },
  parcial: { label: "A medias", cls: "text-forge-warning bg-forge-warning-bg border-forge-warning-border", dot: "bg-forge-warning" },
  falta: { label: "Falta", cls: "text-forge-error bg-forge-error-bg border-forge-error-border", dot: "bg-forge-error" },
  intencional: { label: "Intencional", cls: "text-forge-muted bg-forge-bg border-forge-border", dot: "bg-forge-muted" },
};

export const DIRECCION = {
  titulo: "la pena del colectivo",
  genero: { id: "paranormal", label: "Paranormal" },
  subgenero: { id: "fantasmas", label: "Fantasmas" },
  deQueTrata:
    "José maneja micros de larga distancia de noche y nunca creyó en los casos que cuentan sus compañeros. " +
    "Una noche vuelve solo desde un pueblo y ve por el espejo a una mujer que murió en ese micro. " +
    "Lo toca, casi choca, y descubre un pedestal con su foto al costado de la ruta.",
  efectos: [
    { id: "pavor", label: "Pavor creciente", ayuda: "La inquietud sube acto a acto hasta el clímax." },
    { id: "susto", label: "Susto", ayuda: "Golpes de sorpresa: el miedo llega de repente." },
    { id: "melancolia", label: "Melancolía inquietante", ayuda: "Más pena que miedo: algo queda doliendo." },
    { id: "revelacion", label: "Horror que se revela", ayuda: "Lo peor se entiende recién al final." },
    { id: "otro", label: "Otro", ayuda: "Contalo con tus palabras." },
  ],
  efecto: "pavor",
  final: "José le deja flores y el alma de la mujer descansa en paz: no la vuelve a ver.",
  finalIntencional: true,
  protagonista: { nombre: "José", queHace: "Chofer de micros de larga distancia, turno noche" },
  narrador: "José",
  comoLoCuenta: [
    { id: "caso", label: "Como un caso entre amigos", ejemplo: "«Mirá, yo no creía en nada de eso, pero esa noche…»" },
    { id: "confesion", label: "Como una confesión", ejemplo: "«Nunca se lo conté a nadie. Ni a mi mujer.»" },
    { id: "cronica", label: "Como una crónica seca", ejemplo: "«Eran las tres y diez. La terminal estaba vacía.»" },
    { id: "literario", label: "Literario", ejemplo: "«La terminal dormía bajo una luz que parpadeaba sin ganas.»" },
  ],
  comoLoCuentaElegido: "caso",
};

export interface Pregunta {
  criterio: string;
  nombre: string;
  estado: Semaforo;
  porQue: string;
  pregunta?: string;
  opciones?: string[];
  respuesta?: string;
}

export const TALLER = {
  ronda: 2,
  maxRondas: 5,
  fin: {
    tipo: "abierto" as "abierto" | "cumple" | "sin_preguntas" | "no_suma",
    texto: "Quedan 2 preguntas abiertas. Podés responderlas, analizar de nuevo o pasar a la escaleta cuando quieras.",
  },
  preguntas: [
    {
      criterio: "vulnerabilidad",
      nombre: "Qué lo expone",
      estado: "falta",
      porQue: "Si a José le pasa por algo que hizo o que cree, el miedo pesa más que si le pasa por azar.",
      pregunta: "¿Qué hace o cree José que lo deja expuesto a esta mujer?",
      opciones: [
        "Se burla de los compañeros que cuentan casos",
        "Maneja cansado y no para nunca, ni cuando se lo piden",
        "Nunca se perdonó no haber parado aquella noche",
      ],
    },
    {
      criterio: "en_juego",
      nombre: "Qué está en juego",
      estado: "parcial",
      porQue: "Si José no puede perder nada, el lector no teme por él: solo mira.",
      pregunta: "Si el micro se sale de la ruta, ¿qué pierde José además del susto?",
      opciones: [
        "El trabajo: ya tiene una advertencia por llegar tarde",
        "Llegar a tiempo con su hija internada",
        "La confianza de los compañeros, que lo van a tomar por loco",
      ],
    },
    {
      criterio: "meta",
      nombre: "Qué quiere José",
      estado: "cumple",
      porQue: "Una meta concreta le da a la amenaza algo que frustrar.",
      respuesta: "Llegar antes del amanecer: su hija está internada y le prometió estar a la mañana.",
    },
    {
      criterio: "historia_secreta",
      nombre: "La historia secreta",
      estado: "cumple",
      porQue: "Un cuento cuenta dos historias: la que se ve y la que explica por qué le pasa a él.",
      respuesta:
        "José manejaba el micro la noche que la mujer se descompensó: ella le pidió que parara y él siguió para no atrasarse. Nunca se lo contó a nadie.",
    },
    {
      criterio: "final",
      nombre: "El final",
      estado: "intencional",
      porQue: "El final es la marca que queda. Lo elegiste vos: el asistente no lo va a discutir.",
      respuesta: "El alma descansa en paz después de las flores.",
    },
  ] as Pregunta[],
};

export interface Acto {
  numero: number;
  nombre: string;
  intensidad: string;
  meta: string;
  hechos: string[];
  cambio: { de: string; a: string };
  escenario: string;
  reglas: string[];
  seGuarda: string;
  siembra: string[];
  cobra: string[];
  decisiones: string[];
  avisos: string[];
}

export const ESCENARIOS = [
  "La estación del pueblo",
  "El interior del micro",
  "La ruta de noche",
  "El pedestal al costado de la ruta",
];

export const PERSONAJES = ["José", "El sereno de la estación"];

/** Lo que el taller dejó decidido (respuestas + intencionales) y si la escaleta lo usa. */
export const DECISIONES = [
  { nombre: "Qué quiere José", integrada: true },
  { nombre: "La historia secreta", integrada: false },
  { nombre: "El final en paz", integrada: true },
];

export const ESCALETA: Acto[] = [
  {
    numero: 1,
    nombre: "Exposición",
    intensidad: "baja",
    meta: "Terminar el turno y salir cuanto antes: le prometió a su hija estar a la mañana.",
    hechos: [
      "José termina su turno en la estación, agotado, apurado por volver.",
      "Recuerda de pasada a una pasajera con un ramo de flores que le pidió bajar.",
      "Le pregunta al sereno por la mujer que murió en el micro; el sereno le contesta con evasivas.",
      "Sube al micro vacío y limpia el espejo con un trapo, convencido de que era un reflejo.",
    ],
    cambio: { de: "Cansado pero tranquilo", a: "Inquieto: algo en el espejo no le cierra" },
    escenario: "La estación del pueblo",
    reglas: [],
    seGuarda: "Que José manejaba el micro la noche que murió la mujer.",
    siembra: ["El ramo de la pasajera", "La promesa a la hija"],
    cobra: [],
    decisiones: ["Qué quiere José"],
    avisos: [],
  },
  {
    numero: 2,
    nombre: "Acción ascendente",
    intensidad: "media",
    meta: "Convencerse de que es el cansancio y seguir manejando.",
    hechos: [
      "José arranca y en el espejo ve a una mujer de pelo atado en el último asiento.",
      "Frena de golpe y se da vuelta: el asiento está vacío.",
      "Prende la radio para distraerse, pero la señal se corta cada vez que la mira.",
    ],
    cambio: { de: "Racionaliza todo", a: "Empieza a dudar de lo que ve" },
    escenario: "La ruta de noche",
    reglas: ["Solo aparece cuando José está solo en el micro."],
    seGuarda: "Quién es la mujer.",
    siembra: [],
    cobra: [],
    decisiones: [],
    avisos: ["El espejo es el encuentro de los actos 2, 3 y 4: probá otro tipo de encuentro en alguno (un sonido, el olor a flores)."],
  },
  {
    numero: 3,
    nombre: "Clímax",
    intensidad: "alta",
    meta: "No perder el control del micro.",
    hechos: [
      "La mujer aparece en el asiento de al lado, más cerca que nunca.",
      "José siente un toque frío en el hombro.",
      "Un roce en la cara lo hace soltar el volante y el micro se sale unos metros de la ruta.",
      "Recupera el control al borde de la banquina.",
    ],
    cambio: { de: "Asustado pero en control", a: "Al borde del colapso" },
    escenario: "La ruta de noche",
    reglas: ["Solo aparece cuando José está solo en el micro."],
    seGuarda: "Por qué la mujer lo busca a él.",
    siembra: [],
    cobra: [],
    decisiones: [],
    avisos: [],
  },
  {
    numero: 4,
    nombre: "Acción descendente",
    intensidad: "media-alta",
    meta: "Entender qué le pasó.",
    hechos: [
      "José frena donde se salió de la ruta y baja, temblando.",
      "Encuentra un pedestal con la foto de la mujer que vio en el espejo.",
      "En la foto, la mujer sostiene el mismo ramo que él recuerda.",
      "Deja unas flores en el pedestal.",
    ],
    cambio: { de: "Aterrado", a: "Con una culpa que no puede nombrar" },
    escenario: "El pedestal al costado de la ruta",
    reglas: [],
    seGuarda: "—",
    siembra: [],
    cobra: ["El ramo de la pasajera"],
    decisiones: [],
    avisos: [
      "«Deja unas flores en el pedestal» también está en el Acto 5: dejalo en uno solo.",
      "La historia secreta no aparece en ningún acto: ¿la revela José acá, frente a la foto?",
    ],
  },
  {
    numero: 5,
    nombre: "Desenlace",
    intensidad: "baja",
    meta: "Hacer las paces con la mujer y con él mismo.",
    hechos: [
      "Días después, José para el micro en el mismo lugar.",
      "Deja flores en el pedestal.",
      "Ya no la vuelve a ver en el espejo.",
      "Sigue viaje para llegar a tiempo con su hija.",
    ],
    cambio: { de: "Atormentado", a: "En paz, con una pena que le queda" },
    escenario: "El pedestal al costado de la ruta",
    reglas: [],
    seGuarda: "Nada: acá se cierra todo.",
    siembra: [],
    cobra: ["La promesa a la hija"],
    decisiones: ["El final en paz", "Qué quiere José"],
    avisos: [],
  },
];
