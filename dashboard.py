import pandas as pd
import dash
from dash import dcc, html, Input, Output
import plotly.express as px

# Load CSV
df = pd.read_csv('summarydata.csv')  # Replace with your actual file name
df['date'] = pd.to_datetime(df['date'])
df['status'] = df['potential_threat'].apply(lambda x: 'Valid' if x.lower() == 'no' else 'Invalid')

# Initialize Dash app
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "Threat Dashboard"

# Layout
app.layout = html.Div([
    html.H2("Query Threat Dashboard", style={'textAlign': 'center'}),

    dcc.Dropdown(
        id='metric-selector',
        options=[
            {'label': 'Valid Queries', 'value': 'valid'},
            {'label': 'Invalid Queries', 'value': 'invalid'},
            {'label': 'No. of Queries by User', 'value': 'user_count'},
            {'label': 'Environment', 'value': 'env'}
        ],
        value='valid',
        clearable=False,
        style={'width': '50%', 'margin': 'auto'}
    ),

    dcc.Graph(id='pie-chart'),
    dcc.Graph(id='stacked-bar'),
    dcc.Graph(id='line-graph')
])

# Pie Chart
@app.callback(
    Output('pie-chart', 'figure'),
    Input('metric-selector', 'value')
)
def update_pie_chart(metric):
    if metric == 'valid':
        df_filtered = df[df['status'] == 'Valid']
        fig = px.pie(df_filtered, names='env', title='Valid Queries by Environment')
    elif metric == 'invalid':
        df_filtered = df[df['status'] == 'Invalid']
        fig = px.pie(df_filtered, names='env', title='Invalid Queries by Environment')
    elif metric == 'user_count':
        user_counts = df['user'].value_counts().reset_index()
        user_counts.columns = ['user', 'count']
        fig = px.pie(user_counts, names='user', values='count', title='Total Queries per User')
    elif metric == 'env':
        fig = px.pie(df, names='env', title='Queries by Environment')
    return fig

# Stacked Bar Chart - Last 5 Days
@app.callback(
    Output('stacked-bar', 'figure'),
    Input('metric-selector', 'value')
)
def update_stacked_chart(_):
    recent_days = df[df['date'] >= df['date'].max() - pd.Timedelta(days=4)]
    grouped = recent_days.groupby(['date', 'status']).size().reset_index(name='count')
    fig = px.bar(grouped, x='date', y='count', color='status', barmode='stack',
                 title="Valid vs Invalid - Last 5 Days")
    return fig

# Line Graph: Query count per user
@app.callback(
    Output('line-graph', 'figure'),
    Input('metric-selector', 'value')
)
def update_line_chart(_):
    grouped = df.groupby(['user', 'status']).size().reset_index(name='count')
    pivot = grouped.pivot(index='user', columns='status', values='count').fillna(0).reset_index()
    pivot = pivot.sort_values('user')

    fig = px.line(
        pivot,
        x='user',
        y=['Valid', 'Invalid'],
        markers=True,
        labels={'value': 'Query Count', 'user': 'User', 'variable': 'Status'},
        title='Query Count per User (Valid vs Invalid)'
    )

    # Set line colors
    fig.update_traces(line=dict(color='green'), selector=dict(name='Valid'))
    fig.update_traces(line=dict(color='red'), selector=dict(name='Invalid'))

    fig.update_layout(
        yaxis_title='Number of Queries',
        xaxis_title='Users',
        legend_title='Query Type',
        template='plotly_white'
    )

    return fig

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
