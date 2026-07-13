from django.urls import path

from t_invest.views import (
    AccauntCreateView,
    AccauntDeleteView,
    AccauntListView,
    FavoriteInstrumentListView,
    ToggleFavoriteView,
    TradingOperation,
    TraidingTerminal,
    UpdatePortfolio,
    delete_favorite_view,
)

app_name = "t_invest"

urlpatterns = [
    path("accaunt/add/", AccauntCreateView.as_view(), name="accaunt_add"),
    path("accaunt/list", AccauntListView.as_view(), name="accaunt_list"),
    path(
        "accaunt/<int:pk>/portfolio/update",
        UpdatePortfolio.as_view(),
        name="accaunt_portfolio_update",
    ),
    path(
        "accaunt/<int:pk>/delete/",
        AccauntDeleteView.as_view(),
        name="accaunt_delete",
    ),
    path(
        "traid/<int:pk>/", TradingOperation.as_view(), name="trading_operation"
    ),
    path(
        "traid/<int:pk>/favorite_instruments/",
        FavoriteInstrumentListView.as_view(),
        name="favorite_instruments",
    ),
    path(
        "favorites/toggle/<uuid:uid>/",
        ToggleFavoriteView.as_view(),
        name="toggle_favorite",
    ),
    path(
        "favorites/delete/<str:ticker>/",
        delete_favorite_view,
        name="delete_favorite",
    ),
    path(
        "traid/terminal/", TraidingTerminal.as_view(), name="trading_terminal"
    ),
]
