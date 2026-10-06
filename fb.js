// Conexión con Firebase para armador.html y admin.html. Si firebase-config.js no está completo,
// las páginas siguen funcionando como antes (WhatsApp / panel local).
import { firebaseConfig } from "./firebase-config.js";
const listo = (ok, extra) => { window.FB = ok ? extra : null; document.dispatchEvent(new CustomEvent("fbready", { detail: { ok } })); };
try {
  if (!firebaseConfig || !firebaseConfig.apiKey || String(firebaseConfig.apiKey).startsWith("TU_")) throw new Error("sin configurar");
  const V = "10.12.2", B = "https://www.gstatic.com/firebasejs/" + V + "/";
  const { initializeApp } = await import(B + "firebase-app.js");
  const fs = await import(B + "firebase-firestore.js");
  const au = await import(B + "firebase-auth.js");
  const app = initializeApp(firebaseConfig), db = fs.getFirestore(app), auth = au.getAuth(app);
  const quitar = (o) => JSON.parse(JSON.stringify(o, (k, v) => (v === undefined ? null : v)));
  listo(true, {
    // ----- público (armador)
    precios: async () => { const s = await fs.getDoc(fs.doc(db, "publico", "precios")); return s.exists() ? s.data() : null; },
    enviarPedido: async (p) => { const r = await fs.addDoc(fs.collection(db, "pedidos"), { ...quitar(p), creado: fs.serverTimestamp() }); return r.id; },
    // ----- administrador (panel)
    onAuth: (cb) => au.onAuthStateChanged(auth, cb),
    login: (e, p) => au.signInWithEmailAndPassword(auth, e, p),
    logout: () => au.signOut(auth),
    escuchar: (cb, err) => fs.onSnapshot(fs.query(fs.collection(db, "pedidos"), fs.orderBy("creado", "desc")), (snap) => {
      const lista = snap.docs.map((d) => { const x = d.data(); return { ...x, id: d.id, fecha: x.fecha || (x.creado && x.creado.toMillis ? x.creado.toMillis() : Date.now()) }; });
      const nuevos = snap.docChanges().filter((c) => c.type === "added" && !c.doc.metadata.hasPendingWrites).map((c) => c.doc.data().qn);
      cb(lista, nuevos);
    }, err),
    guardar: (id, o) => { const x = quitar(o); delete x.id; delete x.creado; return fs.setDoc(fs.doc(db, "pedidos", id), { ...x, creado: o.creado || fs.serverTimestamp() }, { merge: true }); },
    nuevoId: () => fs.doc(fs.collection(db, "pedidos")).id,
    borrar: (id) => fs.deleteDoc(fs.doc(db, "pedidos", id)),
    leer: async (col, id) => { const s = await fs.getDoc(fs.doc(db, col, id)); return s.exists() ? s.data() : null; },
    escribir: (col, id, o) => fs.setDoc(fs.doc(db, col, id), quitar(o))
  });
} catch (e) { console.info("Firebase no activo:", e.message); listo(false); }
