"""Datos de demostración: usuarios, empresas, cuentas, proyectos y movimientos.

    python -m app.seed

Solo se cargan si la base no tiene empresas (es seguro ejecutarlo varias veces). Los movimientos se
registran con los mismos servicios que usa la API, así que pasan por todas las validaciones y quedan
en la bitácora. Los usuarios de demostración usan la contraseña DEMO_PASSWORD.
"""

import sys
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.core.security import hash_password
from app.core.tiempo import hoy
from app.db.session import SessionLocal
from app.models import (
    AccionBitacora,
    Categoria,
    Cuenta,
    Empresa,
    Moneda,
    Pendiente,
    Proyecto,
    Rol,
    TipoCuenta,
    TipoPendiente,
    Usuario,
)
from app.schemas.movimiento import EntradaCrear, SalidaCrear
from app.services.bitacora import registrar
from app.services.movimientos import crear_entrada, crear_salida, vincular

DEMO_PASSWORD = "Demo2026"
USUARIOS = [("Admin Demo", "admin@demo.local", Rol.ADMIN), ("Ana Contadora", "ana@demo.local", Rol.CONTADOR),
            ("Luis Contador", "luis@demo.local", Rol.CONTADOR)]


def main() -> int:
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Empresa)):
            print("seed: la base ya tiene empresas; no se hace nada")
            return 1

        usuarios = {}
        for nombre, correo, rol in USUARIOS:
            u = db.scalar(select(Usuario).where(Usuario.correo == correo))
            if u is None:
                u = Usuario(nombre=nombre, correo=correo, password_hash=hash_password(DEMO_PASSWORD), rol=rol)
                db.add(u)
                db.flush()
                registrar(db, usuario_id=None, entidad="Usuario", entidad_id=u.id, accion=AccionBitacora.CREAR,
                          detalle={"correo": correo, "rol": rol, "origen": "seed"})
            usuarios[correo] = u
        ana, luis = usuarios["ana@demo.local"], usuarios["luis@demo.local"]

        def empresa(nombre: str, autor: Usuario) -> Empresa:
            e = Empresa(nombre=nombre, creado_por=autor.id)
            db.add(e)
            db.flush()
            return e

        def cuenta(e: Empresa, tipo: TipoCuenta, moneda: Moneda, nombre: str, autor: Usuario, banco: str | None = None,
                   numero: str | None = None) -> Cuenta:
            c = Cuenta(empresa_id=e.id, tipo=tipo, moneda=moneda, nombre=nombre, banco=banco, numero=numero,
                       creado_por=autor.id)
            db.add(c)
            db.flush()
            return c

        def proyecto(nombre: str, descripcion: str, autor: Usuario) -> Proyecto:
            p = Proyecto(nombre=nombre, descripcion=descripcion, creado_por=autor.id)
            db.add(p)
            db.flush()
            return p

        norte = empresa("Constructora del Norte", ana)
        pacifico = empresa("Inmobiliaria Pacífico", luis)
        empresa("Servicios Baja", luis)  # sin cuentas: se agregan después
        c = {
            "norte_bbva": cuenta(norte, TipoCuenta.BANCO, Moneda.MXN, "BBVA MXN", ana, "BBVA", "0123456789"),
            "norte_usd": cuenta(norte, TipoCuenta.BANCO, Moneda.USD, "BBVA USD", ana, "BBVA", "0987654321"),
            "norte_caja": cuenta(norte, TipoCuenta.CAJA, Moneda.MXN, "Caja MXN", ana),
            "pac_banorte": cuenta(pacifico, TipoCuenta.BANCO, Moneda.MXN, "Banorte MXN", luis, "Banorte", "1122334455"),
            "pac_caja": cuenta(pacifico, TipoCuenta.CAJA, Moneda.MXN, "Caja MXN", luis),
            "pac_caja_usd": cuenta(pacifico, TipoCuenta.CAJA, Moneda.USD, "Caja USD", luis),
        }
        torre = proyecto("Torre Reforma", "Edificio de oficinas, 12 niveles", ana)
        palmas = proyecto("Residencial Las Palmas", "40 casas en Rosarito", luis)
        bodega = proyecto("Bodega Industrial", None, ana)
        vincular(db, norte, bodega, ana, automatico=False)
        # Proyecciones (no afectan saldos)
        torre.estimado_ingresos_mxn, torre.estimado_gastos_mxn = Decimal("1500000"), Decimal("900000")
        torre.estimado_ingresos_usd, torre.estimado_gastos_usd = Decimal("25000"), Decimal("15000")
        torre.trabajadores_estimados = 40
        torre.fecha_inicio_estimada, torre.fecha_fin_estimada = hoy() - timedelta(days=60), hoy() + timedelta(days=300)
        palmas.estimado_ingresos_mxn, palmas.estimado_gastos_mxn = Decimal("4000000"), Decimal("2600000")
        palmas.trabajadores_estimados = 60
        cat = {}
        for nombre in ("Anticipos", "Ventas", "Materiales", "Nómina", "Servicios", "Depósitos"):
            cat[nombre] = Categoria(nombre=nombre, creado_por=ana.id)
            db.add(cat[nombre])
        db.flush()
        db.commit()

        d = hoy()

        def dia(n: int):
            return d - timedelta(days=n)

        def ent(autor, p, cta, n, monto, pct="0", concepto=None, ref=None, categoria=None):
            crear_entrada(db, EntradaCrear(proyecto_id=p.id, empresa_id=cta.empresa_id, cuenta_id=cta.id, fecha=dia(n),
                                           forma="efectivo" if cta.tipo == TipoCuenta.CAJA else "transferencia",
                                           monto=Decimal(monto), porcentaje_gasto=Decimal(pct), concepto=concepto,
                                           referencia=ref, categoria_id=cat[categoria].id if categoria else None),
                          autor)

        def sal(autor, p, cta, n, monto, concepto, beneficiario=None, categoria=None, factura=False):
            crear_salida(db, SalidaCrear(proyecto_id=p.id, empresa_id=cta.empresa_id, cuenta_id=cta.id, fecha=dia(n),
                                         forma="efectivo" if cta.tipo == TipoCuenta.CAJA else "transferencia",
                                         monto=Decimal(monto), concepto=concepto, beneficiario=beneficiario,
                                         categoria_id=cat[categoria].id if categoria else None,
                                         requiere_factura=factura), autor)

        # El dinero que ya había en las cuentas al empezar también entra por un proyecto.
        ent(ana, torre, c["norte_bbva"], 60, "250000", concepto="Saldo de apertura")
        ent(ana, torre, c["norte_caja"], 60, "15000", concepto="Saldo de apertura")
        ent(ana, torre, c["norte_bbva"], 55, "500000", "3", "Anticipo 1", "SPEI 88213", "Anticipos")
        ent(ana, torre, c["norte_caja"], 48, "80000", "5", "Pago en efectivo")
        ent(luis, torre, c["pac_banorte"], 40, "300000", "2.5", "Anticipo 2", "SPEI 90122", "Anticipos")
        ent(ana, torre, c["norte_usd"], 35, "20000", "1", "Pago de socio", "WIRE 5512")
        ent(luis, palmas, c["pac_banorte"], 30, "750000", "3", "Venta casa 1 y 2", categoria="Ventas")
        ent(luis, palmas, c["pac_caja"], 21, "120000", concepto="Apartado casa 7", categoria="Ventas")
        ent(luis, palmas, c["pac_caja_usd"], 14, "8000", "2", "Apartado casa 12", categoria="Ventas")
        ent(ana, bodega, c["norte_bbva"], 10, "200000", concepto="Anticipo")
        sal(ana, torre, c["norte_bbva"], 45, "180000", "Acero y varilla", "Aceros del Pacífico SA", "Materiales", True)
        sal(ana, torre, c["norte_caja"], 44, "35000", "Nómina de obra, semana 1", categoria="Nómina")
        sal(luis, torre, c["pac_banorte"], 25, "120000", "Concreto premezclado", "Cemex", "Materiales", True)
        sal(ana, torre, c["norte_usd"], 20, "6500", "Elevador, anticipo", "Otis")
        sal(luis, palmas, c["pac_banorte"], 18, "260000", "Urbanización", "Pavimentos Baja", "Servicios", True)
        sal(luis, palmas, c["pac_caja"], 7, "45000", "Nómina de obra", categoria="Nómina")
        sal(ana, bodega, c["norte_bbva"], 3, "95000", "Estructura metálica", "Naves del Norte", "Materiales")
        # Depósito del efectivo al banco: salida de la caja y entrada sin % al banco, del mismo proyecto.
        sal(ana, torre, c["norte_caja"], 30, "40000", "Depósito del efectivo al banco", categoria="Depósitos")
        ent(ana, torre, c["norte_bbva"], 30, "40000", concepto="Depósito del efectivo de la caja", categoria="Depósitos")
        sal(luis, palmas, c["pac_caja"], 5, "50000", "Depósito del efectivo al banco", categoria="Depósitos")
        ent(luis, palmas, c["pac_banorte"], 5, "50000", concepto="Depósito del efectivo de la caja", categoria="Depósitos")
        for proy, tipo, concepto, contraparte, moneda, monto, dias in (
                (torre, TipoPendiente.POR_COBRAR, "Estimación 3", "Grupo Reforma", Moneda.MXN, "350000", 20),
                (torre, TipoPendiente.POR_PAGAR, "Acero, segunda entrega", "Aceros del Pacífico SA", Moneda.MXN, "140000", -5),
                (torre, TipoPendiente.POR_PAGAR, "Elevador, finiquito", "Otis", Moneda.USD, "6500", 45),
                (palmas, TipoPendiente.POR_COBRAR, "Venta casa 3", "Cliente particular", Moneda.MXN, "380000", 30)):
            db.add(Pendiente(proyecto_id=proy.id, tipo=tipo, concepto=concepto, contraparte=contraparte, moneda=moneda,
                             monto=Decimal(monto), fecha_vencimiento=hoy() + timedelta(days=dias), creado_por=ana.id))
        db.commit()
    print(f"seed: datos de demostración cargados. Usuarios: {', '.join(c for _, c, _ in USUARIOS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
