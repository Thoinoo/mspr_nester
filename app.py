from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from sqlalchemy.ext.declarative import DeclarativeMeta
from typing import List
from fastapi.middleware.cors import CORSMiddleware

# Création de l'application et configuration de la base de données
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permet toutes les origines (vous pouvez aussi spécifier une origine spécifique)
    allow_credentials=True,  # Autoriser les informations d'identification
    allow_methods=["*"],  # Permet toutes les méthodes HTTP (GET, POST, DELETE, etc.)
    allow_headers=["*"],  # Permet tous les en-têtes
)

DATABASE_URL = "sqlite:///./data.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base: DeclarativeMeta = declarative_base()

# Modèles de base de données
class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    computers = relationship("Computer", back_populates="client", cascade="all, delete")

class Computer(Base):
    __tablename__ = "computers"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String, unique=True, index=True)
    latency = Column(String)
    hostname = Column(String)
    client_id = Column(Integer, ForeignKey("clients.id"))
    client = relationship("Client", back_populates="computers")
    ports = relationship("Port", back_populates="computer", cascade="all, delete")

class Port(Base):
    __tablename__ = "ports"

    id = Column(Integer, primary_key=True, index=True)
    port_number = Column(String)
    service_name = Column(String)
    computer_id = Column(Integer, ForeignKey("computers.id"))
    computer = relationship("Computer", back_populates="ports")

# Création des tables
Base.metadata.create_all(bind=engine)

# Routes FastAPI
@app.get("/")
def read_root():
    return {"message": "Bienvenue sur l'API FastAPI. Consultez /docs pour la documentation."
            }

# Créer des clients à partir d'un tableau JSON
@app.post("/clients/")
def create_clients(data: List[dict]):
    session = SessionLocal()
    try:
        for client_data in data:
            client_name = client_data.get("client")
            computers = client_data.get("computers")

            if not client_name or not computers:
                raise HTTPException(status_code=400, detail="Invalid data format")

            # Vérifier si le client existe déjà
            existing_client = session.query(Client).filter(Client.name == client_name).first()
            if existing_client:
                raise HTTPException(status_code=400, detail=f"Client '{client_name}' already exists")

            # Création du client
            client = Client(name=client_name)
            session.add(client)
            session.flush()  # Nécessaire pour obtenir l'ID du client avant de créer les ordinateurs

            # Création des ordinateurs et des ports
            for ip, computer_data in computers.items():
                computer = Computer(
                    ip_address=ip,
                    latency=computer_data.get("latency"),
                    hostname=computer_data.get("hostname"),
                    client_id=client.id,
                )
                session.add(computer)
                session.flush()

                for port, service in computer_data.get("ports", {}).items():
                    port_entry = Port(
                        port_number=port,
                        service_name=service,
                        computer_id=computer.id,
                    )
                    session.add(port_entry)

        session.commit()
        return {"message": "Clients and computers created successfully"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# Lire tous les clients et leurs ordinateurs
@app.get("/clients/")
def get_all_clients():
    session = SessionLocal()
    try:
        clients = session.query(Client).all()
        if not clients:
            return {"message": "No clients found"}

        result = []
        for client in clients:
            result.append({
                "client": client.name,
                "computers": [
                    {
                        "ip_address": computer.ip_address,
                        "latency": computer.latency,
                        "hostname": computer.hostname,
                        "ports": {port.port_number: port.service_name for port in computer.ports},
                    }
                    for computer in client.computers
                ],
            })
        return result
    finally:
        session.close()

@app.put("/clients/{client_name}")
def update_client(client_name: str, data: dict):
    session = SessionLocal()
    try:
        client = session.query(Client).filter(Client.name == client_name).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Mettre à jour les ordinateurs
        for ip, computer_data in data.get("computers", {}).items():
            computer = session.query(Computer).filter(Computer.ip_address == ip, Computer.client_id == client.id).first()
            if computer:
                computer.latency = computer_data.get("latency", computer.latency)
                computer.hostname = computer_data.get("hostname", computer.hostname)

                # Mettre à jour les ports
                for port, service in computer_data.get("ports", {}).items():
                    port_entry = session.query(Port).filter(Port.computer_id == computer.id, Port.port_number == port).first()
                    if port_entry:
                        port_entry.service_name = service
                    else:
                        # Ajouter le port s'il n'existe pas
                        new_port = Port(port_number=port, service_name=service, computer_id=computer.id)
                        session.add(new_port)
            else:
                # Ajouter un nouvel ordinateur si non existant
                new_computer = Computer(
                    ip_address=ip,
                    latency=computer_data.get("latency"),
                    hostname=computer_data.get("hostname"),
                    client_id=client.id,
                )
                session.add(new_computer)

        session.commit()
        return {"message": f"Client '{client_name}' updated successfully"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# Supprimer un client et ses ordinateurs
@app.delete("/clients/{client_name}")
def delete_client(client_name: str):
    session = SessionLocal()
    try:
        client = session.query(Client).filter(Client.name == client_name).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        session.delete(client)
        session.commit()
        return {"message": f"Client '{client_name}' deleted successfully"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# Lancement de l'application
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=57935, reload=True)