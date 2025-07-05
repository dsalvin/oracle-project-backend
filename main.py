import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import os
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import StreamingResponse
import io 

import auth
import models
import schemas
from database import SessionLocal, engine
from prophet import Prophet
from typing import List


# --- App and DB Setup ---
UPLOAD_DIRECTORY = "./uploads"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

models.Base.metadata.create_all(bind=engine)
app = FastAPI(title="Oracle Sales Forecaster API")

# --- ADD SESSION MIDDLEWARE ---
# This must be added for the Google OAuth flow to work.
# IMPORTANT: Change this secret_key to a long, random string in production.
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "a_very_secret_key_for_sessions")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)


# --- CORS MIDDLEWARE CONFIGURATION ---
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://https://oracle-frontend-chi.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Helper Function for Insight Generation (RESTORED) ---
def generate_insight(product_id: str, historical_df: pd.DataFrame, forecast_df: pd.DataFrame) -> str:
    """Analyzes forecast data to generate a simple, actionable insight."""
    last_historical_avg = historical_df['y'].tail(7).mean()
    last_forecast_avg = forecast_df['yhat'].tail(7).mean()

    if pd.isna(last_historical_avg) or last_historical_avg == 0:
        change_percent = float('inf') if last_forecast_avg > 0 else 0
    else:
        change_percent = ((last_forecast_avg - last_historical_avg) / last_historical_avg) * 100

    if change_percent > 15:
        trend_summary = f"shows a strong upward trend. Sales are predicted to increase by approximately {change_percent:.0f}% over the next month."
        recommendation = "Consider increasing stock to meet expected demand."
    elif change_percent > 5:
        trend_summary = f"shows a modest upward trend, with a predicted increase of around {change_percent:.0f}%."
        recommendation = "Ensure stock levels are adequate."
    elif change_percent < -15:
        trend_summary = f"shows a significant downward trend, with sales predicted to decrease by {abs(change_percent):.0f}%."
        recommendation = "Consider running promotions or reducing inventory."
    elif change_percent < -5:
        trend_summary = f"shows a modest downward trend, with a predicted decrease of around {abs(change_percent):.0f}%."
        recommendation = "Monitor sales closely."
    else:
        trend_summary = "is predicted to remain stable."
        recommendation = "Maintain current inventory and marketing strategies."

    return f"Product '{product_id}' {trend_summary} {recommendation}"


# --- Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get('/login/google')
async def login_google(request: Request):
    redirect_uri = request.url_for('auth_google')
    return await auth.oauth.google.authorize_redirect(request, str(redirect_uri))

@app.get('/auth/callback/google')
async def auth_google(request: Request, db: Session = Depends(get_db)):
    try:
        token = await auth.oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Could not authorize Google account.")
    
    user_data = token.get('userinfo')
    if not user_data:
        raise HTTPException(status_code=400, detail="Could not retrieve user info from Google.")

    user_email = user_data['email']
    db_user = db.query(models.User).filter(models.User.email == user_email).first()

    # If user doesn't exist, create a new one
    if not db_user:
        new_user = models.User(
            email=user_email,
            first_name=user_data.get('given_name', ''),
            last_name=user_data.get('family_name', ''),
            hashed_password="" # Social login users don't need a password
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        db_user = new_user

    # Create an access token for our application and redirect to the frontend
    access_token = auth.create_access_token(data={"sub": db_user.email})
    
    # Redirect back to the frontend with the token
    response = RedirectResponse(url=f"http://localhost:5173/auth/callback?token={access_token}")
    return response


@app.get("/export/forecast/")
def export_forecast_csv(
    product_id: str,
    filename: str,
    current_user: models.User = Depends(auth.get_current_user)
):
    file_path = os.path.join(UPLOAD_DIRECTORY, f"user_{current_user.id}_{filename}")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found. Please upload it again.")

    # --- Re-run the core forecasting logic ---
    df = pd.read_csv(file_path)
    product_history = df[df['product_id'] == product_id].copy()
    if product_history.empty:
        raise HTTPException(status_code=404, detail=f"Product ID '{product_id}' not found.")
    if len(product_history) < 30:
        raise HTTPException(status_code=400, detail="Not enough data to export.")

    prophet_df = product_history[['date', 'units_sold']].rename(columns={'date': 'ds', 'units_sold': 'y'})
    prophet_df['ds'] = pd.to_datetime(prophet_df['ds'])
    model = Prophet(daily_seasonality=True)
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=30)
    forecast = model.predict(future)

    # --- Prepare the CSV data ---
    # We'll export the date, prediction, and confidence intervals
    export_df = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].rename(columns={
        'ds': 'date',
        'yhat': 'predicted_sales',
        'yhat_lower': 'predicted_sales_lower_bound',
        'yhat_upper': 'predicted_sales_upper_bound'
    })
    export_df['date'] = export_df['date'].dt.strftime('%Y-%m-%d')

    # --- Create an in-memory CSV file ---
    stream = io.StringIO()
    export_df.to_csv(stream, index=False)

    # --- Create the response ---
    response = StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=forecast_{product_id}.csv"}
    )
    return response


# --- Auth Endpoints ---
@app.post("/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = auth.get_password_hash(user.password)
    # Add the new fields when creating the user object
    new_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        first_name=user.first_name,
        last_name=user.last_name
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


# --- Protected Endpoints ---
@app.post("/upload-csv/")
async def upload_csv(current_user: models.User = Depends(auth.get_current_user), file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")
    file_path = os.path.join(UPLOAD_DIRECTORY, f"user_{current_user.id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    try:
        df = pd.read_csv(file_path)
        required_columns = {'date', 'product_id', 'units_sold', 'price'}
        if not required_columns.issubset(df.columns):
            raise ValueError(f"Missing required columns. Found: {list(df.columns)}")
        if df['units_sold'].lt(0).any() or df['price'].lt(0).any():
            raise ValueError("'units_sold' and 'price' cannot contain negative values.")
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"CSV Validation Error: {e}")
    return {"message": "CSV validated and saved successfully!", "filename": file.filename, "products": df['product_id'].unique().tolist()}

@app.get("/analysis/")
def get_historical_analysis(
    filename: str,
    current_user: models.User = Depends(auth.get_current_user)
):
    file_path = os.path.join(UPLOAD_DIRECTORY, f"user_{current_user.id}_{filename}")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found. Please upload it again.")

    df = pd.read_csv(file_path)

    # --- 1. Calculate Total Revenue Over Time ---
    df['date'] = pd.to_datetime(df['date'])
    df['revenue'] = df['units_sold'] * df['price']
    revenue_over_time = df.groupby('date')['revenue'].sum().reset_index()
    # Format for JSON compatibility
    revenue_over_time['date'] = revenue_over_time['date'].dt.strftime('%Y-%m-%d')
    
    # --- 2. Calculate Top 5 Selling Products ---
    top_products = df.groupby('product_id')['units_sold'].sum().nlargest(5).reset_index()

    return {
        "revenue_over_time": revenue_over_time.to_dict(orient='records'),
        "top_products": top_products.to_dict(orient='records')
    }


@app.get("/forecast/{product_id}")
def get_forecast(product_id: str, filename: str, current_user: models.User = Depends(auth.get_current_user)):
    file_path = os.path.join(UPLOAD_DIRECTORY, f"user_{current_user.id}_{filename}")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found. Please upload it again.")
    df = pd.read_csv(file_path)
    product_history = df[df['product_id'] == product_id].copy()
    if product_history.empty:
        raise HTTPException(status_code=404, detail=f"Product ID '{product_id}' not found.")
    if len(product_history) < 30:
        raise HTTPException(status_code=400, detail="Not enough data. A minimum of 30 data points is required.")
    prophet_df = product_history[['date', 'units_sold']].rename(columns={'date': 'ds', 'units_sold': 'y'})
    prophet_df['ds'] = pd.to_datetime(prophet_df['ds'])
    model = Prophet(daily_seasonality=True)
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=30)
    forecast = model.predict(future)
    
    # --- Generate and use the detailed insight ---
    insight_text = generate_insight(product_id, prophet_df, forecast)
    
    return {
        "product_id": product_id,
        "insight": insight_text,
        "historical_data": prophet_df.to_dict(orient='records'),
        # Include yhat_lower and yhat_upper in the forecast data
        "forecast_data": forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(30).to_dict(orient='records')
    }