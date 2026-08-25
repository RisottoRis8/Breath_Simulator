%% Caratterizzazione Pneumotacografo - Versione Lineare Pura
clear; clc; close all;

% --- PARAMETRI DI CONFIGURAZIONE ---
metodo_interp = 'pchip'; % Tipo di interpolazione (es. 'linear', 'pchip', 'spline')
n_factor = 15;           % Punti interpolazione = n_factor * numero file

% --- SELEZIONE CARTELLA ---
path_cartella = uigetdir('', 'Seleziona cartella con i file CSV');
if isequal(path_cartella, 0), return; end
lista_file = dir(fullfile(path_cartella, 'misura*.csv'));

risultati = []; % Matrice per memorizzare [P_avg, Q_avg, R_calc]

fprintf('\n%-35s | %-10s | %-10s | %-10s\n', 'File Analizzato', 'P_avg [Pa]', 'Q_avg [L/s]', 'R [Pa*s/L]');
fprintf('----------------------------------------------------------------------------\n');

for i = 1:length(lista_file)
    fn = fullfile(path_cartella, lista_file(i).name);
    
    % 1. Estrazione Volume dai Metadati
    v_siringa = NaN;
    fid = fopen(fn, 'r');
    if fid == -1, continue; end
    while ~feof(fid)
        linea = fgetl(fid);
        if ~ischar(linea), break; end
        if contains(linea, 'Capacita', 'IgnoreCase', true)
            parti = strsplit(linea, ',');
            v_siringa = str2double(parti{2});
        end
        if contains(linea, 'Time_s'), break; end
    end
    fclose(fid);
    
    if isnan(v_siringa), continue; end

    % 2. Lettura Dati (Tutto il file)
    try
        % readmatrix salta le righe di testo e carica solo i numeri
        data_raw = readmatrix(fn);
        data_raw(any(isnan(data_raw), 2), :) = []; % Rimuove righe non numeriche
        
        if size(data_raw, 2) < 2, continue; end
        
        t = data_raw(:, 1);
        p = data_raw(:, 2);
        [t, idx] = unique(t); p = p(idx); % Pulisce duplicati temporali
        
        if length(t) < 2, continue; end

        % 3. Calcolo Lineare Semplice
        durata_totale = t(end) - t(1);
        p_avg = mean(p);             % Media aritmetica semplice della pressione
        q_avg = v_siringa / durata_totale; % Flusso medio sull'intera durata
        r_calc = p_avg / q_avg;      % Resistenza calcolata
        
        % Salvataggio dati
        risultati = [risultati; p_avg, q_avg, r_calc];
        fprintf('%-35s | %10.2f | %10.3f | %10.3f\n', lista_file(i).name, p_avg, q_avg, r_calc);
        
    catch
        continue;
    end
end

% --- RIEPILOGO FINALE ---
num_punti = size(risultati, 1);
fprintf('----------------------------------------------------------------------------\n');
fprintf('Analisi completata su %d punti di resistenza.\n\n', num_punti);

if num_punti < 2
    error('Dati insufficienti per generare grafici e interpolazioni.');
end

% --- PREPARAZIONE DATI PER PLOT E INTERPOLAZIONE ---
% Ordiniamo i dati per permettere l'interpolazione corretta
[Q_s, idxQ] = sort(risultati(:, 2)); 
R_sQ = risultati(idxQ, 3);

[P_s, idxP] = sort(risultati(:, 1)); 
R_sP = risultati(idxP, 3);

% Vettori densi per le curve interpolate
num_punti_interp = num_punti * n_factor;
q_interp_vec = linspace(min(Q_s), max(Q_s), num_punti_interp);
p_interp_vec = linspace(min(P_s), max(P_s), num_punti_interp);

r_interp_Q = interp1(Q_s, R_sQ, q_interp_vec, metodo_interp);
r_interp_P = interp1(P_s, R_sP, p_interp_vec, metodo_interp);

% --- GENERAZIONE GRAFICI ---
figure('Color', 'w', 'Name', 'Caratterizzazione Lineare PNT', 'Position', [100 100 1200 500]);

% Grafico 1: Resistenza vs Flusso
subplot(1, 2, 1);
plot(risultati(:, 2), risultati(:, 3), 'ko', 'MarkerFaceColor', 'r', 'DisplayName', 'Dati Medi Lineari');
hold on;
plot(q_interp_vec, r_interp_Q, 'b-', 'LineWidth', 2, 'DisplayName', ['Interp: ' metodo_interp]);
grid on; box on;
xlabel('Flusso Q [L/s]'); ylabel('Resistenza R [Pa*s/L]');
title('Caratterizzazione: Resistenza vs Flusso');
legend('Location', 'best');

% Grafico 2: Resistenza vs Pressione
subplot(1, 2, 2);
plot(risultati(:, 1), risultati(:, 3), 'ko', 'MarkerFaceColor', 'g', 'DisplayName', 'Dati Medi Lineari');
hold on;
plot(p_interp_vec, r_interp_P, 'b-', 'LineWidth', 2, 'DisplayName', ['Interp: ' metodo_interp]);
grid on; box on;
xlabel('Pressione P [Pa]'); ylabel('Resistenza R [Pa*s/L]');
title('Caratterizzazione: Resistenza vs Pressione');
legend('Location', 'best');